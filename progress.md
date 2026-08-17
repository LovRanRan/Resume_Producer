# Resume Producer — 按 JD 定制简历生成器 · 进度追踪

> 一个 AI 简历定制 agent：用户把**所有**基础信息/实习/项目写进一份 master markdown 档案 → 系统存储为 Candidate → 对每一个 Job 链接或 JD，自动挑选最相关的经历、改写 bullet、生成一份**固定格式**的定制简历 PDF。

最后更新：2026-08-16

**仓库**：https://github.com/LovRanRan/Resume_Producer · 主分支 `main`
**Git 工作流**：每完成一个 commit 自动 push 到 GitHub。

---

## 1. 项目目标

核心主线：
**Master 档案（markdown）→ 解析存储 Candidate → 输入 JD（文本/文件/链接）→ AI 筛选 + 改写 → 固定模板渲染 → 简历 PDF**

关键理念：
- **一份 master 档案，无限份定制简历**。用户维护一份"超集"档案（写得越全越好），每份产出简历是它的一个针对性子集。
- **AI 只做取舍和措辞，不编造事实**。所有内容必须来自 master 档案，AI 负责挑选、排序、按 JD 关键词改写 bullet。
- **格式固定**。排版由 LaTeX 模板锁死，AI 不碰格式，保证每份 PDF 都专业、一致、ATS 友好。

## 2. 关键决策记录

- **技术栈：Python 3.12 CLI**（uv 管理），开发最快、PDF/解析生态最好；后续可加 FastAPI 变成服务（v2）。
- **PDF 引擎：XeLaTeX**（本机已装 MacTeX）。排版质量最高、模板固定不跑版、文本可选中（ATS 友好）。架构上渲染器留接口，之后可加 HTML→PDF 引擎。
- **AI 定制：Claude API**（`claude-opus-5` + structured outputs）。读 JD + master 档案，输出结构化的 TailoredResume（选哪些条目、什么顺序、bullet 怎么改写）。防幻觉措施：prompt 明确"只能用档案里的事实"，且输出按条目 ID 引用原文，程序端校验。
- **JD 输入三种方式全做**：粘贴文本（最可靠，先做）、本地文件、URL 自动抓取（尽力而为——很多站点反爬/需登录，抓不到就提示用户粘贴）。
- **多 candidate 支持**：数据模型按 candidate id 组织（`data/<candidate_id>/`），虽然当前主要是单用户自用。
- **中英文简历**：档案可以中英混写；v1 产出以英文简历为主（美国求职场景），模板用 XeLaTeX 天然支持中文，后续可加中文模板。
- **CLI 命名（2026-08-16 定）**：命令统一为 `resume`（原 `rusume` 为笔误）。
- **模板风格（2026-08-16 定）**：经典单栏 ATS 风（Jake's Resume 类），黑白、紧凑、单页。
- **改写尺度（2026-08-16 定）**：AI 可自由改写 bullet 措辞（按 JD 关键词重组、调整强调点），但每条必须引用档案条目 ID，程序端校验数字/事实未被编造。
- **首份档案（2026-08-16 定）**：用用户真实材料整理 master 档案，存 `data/`（gitignore，不进 public repo）；格式设计以真实内容为准。仓库内另维护一份虚构的 `examples/candidate_example.md` 作为格式说明。
- **条目 ID 方案**：ID 从条目标题自动生成 slug（如 `proj-wayfinder`），用户无需手写；ID 稳定，供 AI 输出引用 + 防幻觉校验。
- **单页控制**：渲染后检测 PDF 页数，超页则按 AI 给出的优先级自动裁剪 bullet 重渲，循环到收敛（Phase 3 实现，Phase 2 模板需支持条目粒度增减）。
- **AI 定制引擎设计（2026-08-16 定稿，详见 docs/agent-design.md）**：确定性 pipeline + 三次 LLM 调用（JD 分析 low effort → 选择 → 改写，均结构化输出），非多轮 agent；改写为独立一步，实习/项目的每条 bullet 逐条按 JD 打磨并**逐条给出改写理由**（进报告，原文/改写/理由三栏对照）；程序端防幻觉校验（ID 存在性/数字守恒/技能子集），失败 bullet 附错误原因 LLM 修复一次、仍失败回退原文；skills 允许子集+重排；每次 tailor 产出存档 `data/<id>/outputs/`；成本约 $0.15–0.3/份。

## 3. 技术选型（已定稿 ✅）

- 语言：Python 3.12 + uv
- CLI：Typer
- 数据模型：Pydantic v2
- 档案格式：Markdown（约定 section 结构，见 `examples/candidate_example.md`）
- AI：Anthropic Claude API（`claude-opus-5`，structured outputs，`ANTHROPIC_API_KEY`）
- JD 抓取:httpx + BeautifulSoup(尽力而为)
- 模板：Jinja2 → LaTeX（自定义分隔符避免与 LaTeX 冲突）
- PDF：XeLaTeX（MacTeX）
- 存储：本地 JSON（`data/<candidate_id>/candidate.json` + 产出历史）

## 4. 模块清单

| # | 模块 | 说明 | 状态 |
|---|------|------|------|
| 0 | 项目规划 | progress.md、README、git repo | ✅ 完成 |
| 1 | Candidate 模型 | Pydantic：基础信息/教育/实习/项目/技能，每条目带稳定 ID | ✅ 完成 |
| 2 | Markdown 解析 | master .md → Candidate（约定 section 格式） | ✅ 完成 |
| 3 | 存储层 | `resume add/list/show`，data/ 目录 JSON 持久化 | ✅ 完成 |
| 4 | LaTeX 模板 | 单页、固定格式、ATS 友好的简历模板 | ✅ 完成 |
| 5 | PDF 渲染 | Jinja2 填模板 → XeLaTeX 编译，`resume render` | ✅ 完成 |
| 6 | JD 输入 | 粘贴文本 / 文件 / URL 抓取 | ✅ 完成 |
| 7 | AI 定制引擎 | Claude 筛选条目 + 改写 bullet → TailoredResume，防幻觉校验 | ✅ 完成 |
| 8 | tailor 命令 | `resume tailor --jd ...` 一条命令出定制 PDF + 产出历史 | ✅ 完成 |
| 9 | 关键词覆盖报告 | 显示 JD 关键词覆盖情况 / 缺口提示 | ✅ 完成（并入 report.md） |
| 10 | Web 界面 / 服务化 | FastAPI + 前端（v2） | ⬜ 未开始 |

> 状态：✅ 完成 · 🟡 部分完成 · ⬜ 未开始

## 5. 分阶段计划

### Phase 0 — 构思 & 规划 ✅
- [x] 确认形态（Python CLI）、PDF 引擎（XeLaTeX）、AI 方案（Claude API）、JD 输入方式（三种全做）
- [x] 写 progress.md / README
- [x] 初始化 git repo + GitHub

### Phase 1 — 核心数据层 ✅
- [x] Candidate Pydantic 模型（含条目稳定 ID）
- [x] master markdown 解析器 + 示例档案（格式规范：docs/master-format.md）
- [x] 存储层 + CLI（add / list / show）
- [x] 真实 master 档案导入验证（data/haichuan，17 bullets，零警告）

### Phase 2 — PDF 渲染 ✅
- [x] LaTeX 简历模板（固定格式，classic 单栏 ATS，TeX Gyre Termes）
- [x] Jinja2 渲染（\VAR/\BLOCK 分隔符 + LaTeX 转义过滤器）+ XeLaTeX 编译（返回页数）
- [x] `resume render` 直接渲染 master 档案（不经 AI，用于验证模板）

### Phase 3 — JD 定制（核心）✅
- [x] JD 输入：文本 / 文件 / URL 抓取
- [x] 三段式 structured output：JDAnalysis → TailoredSelection → RewriteResult（逐条改写+理由）
- [x] 防幻觉校验（ID 存在性/数字守恒/技能子集）+ 失败修复一次 + 回退原文
- [x] 单页裁剪循环（按 priority 纯程序裁剪）
- [x] `resume tailor` 端到端：JD → 定制 PDF + report.md（含关键词覆盖）
- [x] 产出历史记录（data/<id>/outputs/<时间戳>-<公司>/ 全套存档）

### Phase 4 — 增强(后续)
- [ ] 关键词覆盖 / 缺口报告
- [ ] 多模板 / 中文模板
- [ ] Cover letter 生成
- [ ] FastAPI 服务化 + Web 界面

## 6. 日志

- 2026-08-16:Phase 0 —— 立项,确定技术方案,初始化 repo。
- 2026-08-16:创建 GitHub repo(LovRanRan/Resume_Producer, public)并推送;修正仓库名笔误;CLI 定名 `resume`;确认模板风格(单栏 ATS)、改写尺度(自由改写+事实校验)、首份档案用真实材料、条目 ID 与单页控制方案。环境验证:XeLaTeX(TeX Live 2025)/uv/Python 3.12 就绪。
- 2026-08-16:Phase 1 完成 —— master 档案格式规范(docs/master-format.md)、Pydantic 模型、markdown 解析器(中英 section 别名、bullet 续行、自动条目 ID)、存储层、`resume add/list/show` CLI。16 pytest + ruff 全绿;用户真实简历(V4.1)整理为 data/haichuan/master.md 并导入验证:2 教育 / 2 经历 / 7 项目 / 5 技能类别 / 17 bullets,零警告。真实档案仅存本地(gitignore)。
- 2026-08-16:Phase 2 完成 —— classic.tex.j2 模板(单栏 ATS,以用户 V4.1 简历版式为基准)、renderer.py(Jinja2 自定义分隔符、单遍 LaTeX 转义、xelatex 编译返回页数)。转义细节:`--` 防连字、`/` 允许断行、`→` 转 \rightarrow。`resume render haichuan` 出 2 页 PDF(完整档案超页属预期),版式经视觉核对。21 tests + ruff 全绿。
- 2026-08-16:Phase 3 设计定稿 —— docs/agent-design.md:三段式 pipeline(JD 分析→选择→改写)、JDAnalysis/TailoredSelection/RewriteResult schema、三层防幻觉校验+修复策略、单页裁剪循环、产出存档结构、模块拆分。用户要求:改写独立成步,实习/项目 bullet 逐条改写并逐条给理由。API 用法经当前文档核对(messages.parse 结构化输出、adaptive thinking、effort)。
- 2026-08-16:Phase 3 完成 —— schemas/validation/fitting/jd_input/llm/prompts/tailor/report 八模块 + `resume tailor` CLI。32 tests + ruff 全绿。真实 API 端到端两轮:AI Engineer 样例 JD,14→10 条选择,数字守恒校验全过(零修复),$0.2/次;报告含逐条改写三栏对照+21/25 关键词覆盖。调优:选择 prompt 加入单页版面预算(9-11 条);模板密度收紧(边距 0.5in、行距/条目距),同一选择从保留 5 条提升到 7 条、高价值 bullet 不再被裁,版面饱满度对齐用户 V4.1 原版。
