# AI 定制引擎设计（Phase 3）

> 定稿于 2026-08-16（同日修订：选择与改写拆为两步，改写带逐条理由）。实现对应模块 6–8。

## 0. 定性

**确定性 pipeline + 三次 LLM 调用**，不是多轮 agent。LLM 只做判断（选哪些条目、怎么措辞），所有计算、校验、裁剪都在 Python 端确定性完成。无工具调用循环。

```
JD 输入(文本/文件/URL)
  → [LLM#1] JD 分析                     → JDAnalysis(结构化, 存档)
  → [LLM#2] 档案(带条目ID)+JDAnalysis   → TailoredSelection(选条目/排序/优先级/skills子集)
  → [LLM#3] 选中的实习&项目 bullet+JD   → RewriteResult(逐条改写+逐条理由, summary 改写)
  → [程序] 防幻觉校验 → 失败 bullet 附错误原因 LLM 修复一次 → 仍失败回退原文
  → [程序] 渲染 + 单页裁剪循环(按 priority)
  → PDF + 产出报告(选择理由/逐条改写理由/关键词覆盖/校验警告)
```

## 1. 三段式调用

| 调用 | 输入 | 输出 | effort |
|------|------|------|--------|
| #1 JD 分析 | JD 原文 | `JDAnalysis` | low |
| #2 选择 | master 档案全文（含条目 ID）+ JDAnalysis | `TailoredSelection` | 默认(high) |
| #3 改写 | 选中的实习/项目 bullet 原文 + JDAnalysis + 档案 summary | `RewriteResult` | 默认(high) |

拆分理由：
- **#1 独立**：可调试（"JD 理解错" vs "选错"分开定位）；JDAnalysis 存档供关键词覆盖报告复用；同一 JD 重复 tailor 不重复分析。
- **#2 / #3 拆开（2026-08-16 用户要求）**：选择只处理 ID 和排序，输出小而稳；改写是独立专注的一步——只看选中的 bullet，逐条按 JD 打磨措辞，并**逐条给出改写理由**（贴合了 JD 的哪些 must-have/关键词、强调点怎么移的）。理由进产出报告，用户能逐条审查"AI 为什么这么改"。防幻觉校验和修复循环也天然只作用于 #3 的输出。

### JDAnalysis schema

```python
class JDAnalysis(BaseModel):
    role_title: str
    company: str | None
    seniority: str            # e.g. "new grad", "junior", "senior"
    must_haves: list[str]     # 硬性要求
    nice_to_haves: list[str]
    keywords: list[str]       # ATS 关键词(技术名词、领域词)
    domain: str | None        # 业务领域信号
```

### TailoredSelection schema（LLM#2）

```python
class SelectedBullet(BaseModel):
    bullet_id: str          # 必须指向档案真实 bullet
    priority: int           # 全局裁剪优先级, 越大越先被裁

class SelectedEntry(BaseModel):
    entry_id: str
    bullets: list[SelectedBullet]

class SkillLine(BaseModel):
    category_id: str
    items: list[str]        # 原类别 items 的子集, 按 JD 相关性重排

class TailoredSelection(BaseModel):
    projects: list[SelectedEntry]    # 按展示顺序
    experience: list[SelectedEntry]
    skills: list[SkillLine]
    rationale: str                   # 整体选择理由(选了谁/没选谁/为什么)
```

- 教育条目不经 LLM，默认全保留。
- prompt 中给排版预算指导（约 3–4 个项目、每条目 2–3 bullets），让首次渲染就接近单页。

### RewriteResult schema（LLM#3）

```python
class RewrittenBullet(BaseModel):
    source_bullet_id: str
    text: str               # 改写文本(允许与原文相同)
    reason: str             # 逐条改写理由: 贴合了 JD 的哪些点、强调点如何调整

class RewriteResult(BaseModel):
    summary: str            # 按 JD 改写的 summary(受事实约束)
    summary_reason: str
    bullets: list[RewrittenBullet]  # 覆盖 #2 选中的全部实习/项目 bullet
```

- #3 输出缺失的 bullet（漏改）→ 使用原文，警告进报告。
- 改写只能基于源 bullet 的事实；JD 关键词只用于措辞与强调，不得引入档案外事实。

## 2. 防幻觉校验（程序端）

依托 Phase 1 的 `Candidate.entry_index()` / `bullet_index()`：

1. **ID 存在性**（作用于 #2、#3）：所有 `entry_id` / `bullet_id` / `category_id` / `source_bullet_id` 必须存在于档案；#3 的 `source_bullet_id` 还必须在 #2 选中集合内。无效引用丢弃并警告。
2. **数字守恒**（作用于 #3）：改写文本中的每个数字 token（`49`、`95%`、`2.9K`、`396K`、`12x`、`top-k=6`…）必须能在源 bullet 文本中找到（数字归一化后集合比对）。数字是最危险且最可程序化校验的幻觉。
3. **技能子集**（作用于 #2）：`SkillLine.items` 每项必须 ∈ 原类别 items（大小写/空白归一化后比对），防止塞入"JD 要求但档案没有"的技能。
4. **Summary 校验**：同数字守恒，源为整个档案文本。

**失败处理（2026-08-16 定）**：失败 bullet 附具体错误原因（"数字 87% 不在源文本中"）发起一次 LLM 修复调用（仍在 #3 的职责内）；修复后仍失败 → 回退档案原文。所有回退/修复记录写入产出报告。

## 3. 单页控制（纯程序循环）

```
render → 页数 == 1 ? 完成
       → 超页: 在所有 bullet 中裁掉 priority 最大者(约束: 每条目至少保留 1 bullet)
       → bullet 裁完仍超页: 整条目按其 bullet 最低优先级依次裁掉
       → 重渲, 循环(上限 ~15 次, 防御性)
```

裁剪不再调用 LLM。priority 由 LLM#2 在选择时一次性给出。

## 4. API 层

- **模型**：`claude-opus-5`（$5/$25 每 MTok）。
- **结构化输出**：`client.messages.parse(..., output_format=PydanticModel)` → `response.parsed_output`，schema 即上面的 Pydantic 类（structured outputs 不支持递归 schema 与数值约束——本设计的 schema 均为平坦结构，无此问题）。
- **单入口**：所有 LLM 调用经 `llm.py` 一个函数走，统一模型/effort/重试/refusal 处理/用量记录。
- **thinking**：adaptive（默认开启，不传参数）；`output_config.effort`：#1 `low`，#2/#3 默认。
- **边界**：处理 `stop_reason == "refusal"`（读 content 前先检查）；SDK 自带 429/5xx 重试。
- **成本**：一次 tailor 三次调用 ≈ **$0.15–0.3/份**（#3 输入只含选中 bullet，不大；含修复调用时略高）。

## 5. 产出历史

```
data/<candidate_id>/outputs/<YYYYMMDD-HHMMSS>-<company-slug>/
  jd.txt              # JD 原文
  jd_analysis.json    # LLM#1 产物
  selection.json      # LLM#2 产物
  rewrite.json        # LLM#3 产物(校验+修复后, 含逐条理由)
  resume.tex
  resume.pdf
  report.md           # 整体选择理由、逐条改写理由(原文 vs 改写 vs 理由)、
                      # 关键词覆盖、校验警告/回退记录、裁剪记录、用量成本
```

可复现、可回看、可对比多个 JD 的产出。report.md 的逐条改写理由采用三栏式：**原文 → 改写后 → 理由**。

## 6. 测试策略

- **单元测试（不花钱）**：数字提取/校验器、技能子集校验、裁剪循环、Selection+Rewrite → Candidate 子集变换、漏改 bullet 回退，全部用手写 fixture。
- **集成测试（花钱，手动）**：`RESUME_LIVE_TEST=1 uv run pytest -m live` 真实调用 API 端到端；平时 CI 跳过。

## 7. 模块拆分

| 文件 | 职责 |
|------|------|
| `jd_input.py` | JD 三种输入方式（文本/文件/URL 抓取 httpx+bs4 尽力而为） |
| `llm.py` | LLM 单入口：parse 调用封装、effort、refusal、用量统计 |
| `schemas.py` | JDAnalysis / TailoredSelection / RewriteResult 等 Pydantic 模型 |
| `tailor.py` | pipeline 编排：分析→选择→改写→校验→修复→子集变换 |
| `validation.py` | 防幻觉校验器（纯函数） |
| `fitting.py` | 单页裁剪循环（调 renderer） |
| `report.py` | report.md 生成（含逐条改写理由三栏对照） |
| `cli.py` | `resume tailor <id> --jd-file/--jd-url/交互粘贴` |
