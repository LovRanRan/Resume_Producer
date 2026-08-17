# Master 档案格式规范

一份 master markdown 档案 = 一个候选人的全部素材超集。`resume add` 将其解析为结构化的 Candidate 并存储；之后每份定制简历都是它的子集。

完整示例见 [`examples/candidate_example.md`](../examples/candidate_example.md)。

## 总体结构

- `# 任意标题` — 文件首行标题，仅作注释用，解析器忽略。
- `## Section 名` — 六个已知 section（大小写不敏感，支持中文别名）：

  | Section | 别名 |
  |---------|------|
  | `Basic Info` | `Basics`, `基础信息`, `个人信息` |
  | `Education` | `教育`, `教育经历` |
  | `Experience` | `Work Experience`, `实习`, `经历`, `工作经历`, `实习经历` |
  | `Projects` | `项目`, `项目经历` |
  | `Skills` | `Technical Skills`, `技能` |
  | `Additional` | `其他`, `附加` |

  未知 section 会被跳过并产生警告。

## Basic Info

直接写 `Key: value` 行（无 `###` 条目）：

```markdown
## Basic Info
Name: Jane Doe            ← 必填
Location: San Francisco, CA
Email: jane@example.com
Phone: +1 (555) 000-1234
LinkedIn: https://linkedin.com/in/janedoe
GitHub: https://github.com/janedoe
Summary: 一句话定位。可以跨多行，
  紧随其后的非空行会被拼接进 Summary。
```

规则：`Name / Location / Email / Phone / Summary` 是固定字段；**其余任何 value 以 `http` 开头的 key 都会收进 `links`**（key 作为链接标签），所以 Website、Portfolio 等随便加。

## Education / Experience / Projects

每个条目以 `### 名称` 开头（Education 的名称 = 学校，Experience 的 = 公司，Projects 的 = 项目名），后跟 `Key: value` 元数据行，再跟 `- ` bullet 列表：

```markdown
## Experience

### Acme Corp
Title: Software Engineer Intern
Location: Remote
Dates: Jun 2025 – Sep 2025

- Bullet 一条一行；写长了可以换行，
  后续行会自动拼接（不要以 `- ` 或 `Key:` 开头即可）。
- 第二条 bullet。
```

各 section 认识的元数据 key（大小写不敏感）：

- **Education**：`Degree`, `Location`, `Dates`, `Coursework`, `Notes`
- **Experience**：`Title`, `Location`, `Dates`
- **Projects**：`Tagline`（一句话描述）, `Stack`（技术栈行）, `Link`（可重复多行，或 `Links:` 逗号分隔）

## Skills

一行一个类别，格式 `- 类别名: 逗号分隔的技能`：

```markdown
## Skills
- Languages: Python, TypeScript, SQL
- AI / Agents: LangGraph, MCP, RAG
```

## 条目 ID（自动生成，无需手写）

解析时每个条目自动获得稳定 ID：section 前缀 + 名称 slug，如 `proj-wayfinder`、`exp-acme-corp`、`edu-new-york-university`；bullet 获得 `<条目ID>-b1`、`-b2`……AI 定制输出必须按这些 ID 引用条目，程序端据此做防幻觉校验。

注意：bullet ID 按顺序编号，**在条目中间插入/删除 bullet 会使其后的 bullet ID 位移**——不影响正常使用（每次 tailor 都基于当前档案重新解析），只是别在历史产出记录里假设 bullet ID 跨版本稳定。

## 建议

- 档案写得越全越好——bullet 多写、写细，AI 只会挑选和改写，不会补充。
- 中英混写没问题；v1 产出以英文简历为主。
- 真实档案放 `data/`（已 gitignore），不要提交到 public repo。
