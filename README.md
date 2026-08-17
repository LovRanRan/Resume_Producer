# Resume Producer — 按 JD 定制简历生成器

一份 **master markdown 档案** 装下你所有的基础信息、实习、项目 → 针对每个 Job 链接或 JD，AI 自动挑选最相关的经历、改写 bullet → 产出**固定格式**、ATS 友好的定制简历 PDF。

> 进度见 [`progress.md`](./progress.md)。

## 核心理念

- **一份档案，无限简历**：master 档案写得越全越好，每份简历是它的针对性子集。
- **AI 只做取舍和措辞，不编造事实**：所有内容必须来自档案，程序端校验。
- **格式锁死**：排版由 LaTeX 模板固定，每份 PDF 一致、专业。

## 技术栈

- Python 3.12 + uv · Typer CLI · Pydantic v2
- AI:Anthropic Claude API(structured outputs)
- PDF:Jinja2 → XeLaTeX(需要 MacTeX / TeX Live)
- JD 输入:粘贴文本 / 本地文件 / URL 抓取

## 本地运行

```bash
uv sync

# 配置 API Key
cp .env.example .env        # 填入 ANTHROPIC_API_KEY

# 1) 导入你的 master 档案(格式见 examples/candidate_example.md)
uv run rusume add examples/candidate_example.md

# 2) 不经 AI 直接渲染完整简历(验证模板)
uv run rusume render <candidate_id>

# 3) 按 JD 定制(核心功能)
uv run rusume tailor <candidate_id> --jd-file jd.txt
uv run rusume tailor <candidate_id> --jd-url "https://..."
uv run rusume tailor <candidate_id>            # 交互式粘贴 JD
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `rusume add <file.md>` | 解析 master 档案并存储为 candidate |
| `rusume list` | 列出所有 candidate |
| `rusume show <id>` | 查看 candidate 详情 |
| `rusume render <id>` | 完整档案直接渲染 PDF(不经 AI) |
| `rusume tailor <id> --jd-file/--jd-url` | 按 JD 生成定制简历 PDF |
