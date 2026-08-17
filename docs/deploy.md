# 部署指南

架构：Next.js 前端（Vercel）+ FastAPI 后端（任意容器平台，镜像含 XeLaTeX）。

## 本地开发

```bash
# 后端（端口 8001，见 .claude/launch.json / web/.env.local）
uv run resume api --port 8001

# 前端
npm --prefix web run dev -- --port 3001
```

## 后端（Docker）

```bash
docker build -t resume-producer-api .
docker run -p 8000:8000 \
  -v resume_data:/app/data \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e RESUME_API_TOKEN=<随机长字符串> \
  -e RESUME_CORS_ORIGINS=https://<你的前端域名> \
  resume-producer-api
```

- 镜像基于 python:3.12-slim + texlive-xetex，约 1.5–2 GB（LaTeX 是大头）。
- `data/` 通过 volume 持久化：档案、产出历史都在里面，**含个人信息，勿公开**。
- 适配 Railway / Fly.io / Cloud Run：直接用仓库根 Dockerfile；平台注入 `PORT` 时把 CMD
  的端口改成 `--port ${PORT}` 或在平台面板配置。

### 环境变量

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_API_KEY` | 必填，Claude API key |
| `RESUME_API_TOKEN` | 强烈建议：设置后所有 API 要求 Bearer token；前端首页可填入（存 localStorage） |
| `RESUME_CORS_ORIGINS` | 前端域名白名单，逗号分隔（默认 localhost:3000/3001） |
| `RESUME_DATA_DIR` | 数据目录（Docker 内默认 /app/data） |
| `RESUME_MODEL` | 覆盖默认模型（默认 claude-opus-5） |

## 前端（Vercel）

1. 仓库导入 Vercel，Root Directory 选 `web/`
2. 环境变量：`NEXT_PUBLIC_API_URL=https://<后端域名>`
3. 部署后在页面里填入 `RESUME_API_TOKEN`（连接失败提示框中）

## 安全注意

- 这是**单用户**应用：token 只是一道门，不是多租户隔离。不要把后端裸奔在公网（不设 token）。
- 真实档案/产出永远只在后端 volume 里；仓库和前端不含任何个人数据。
