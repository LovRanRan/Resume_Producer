# Resume Producer API — Python 3.12 + XeLaTeX（TeX Gyre 字体）
# 构建:  docker build -t resume-producer-api .
# 运行:  docker run -p 8000:8000 -v resume_data:/app/data \
#          -e ANTHROPIC_API_KEY=sk-ant-... -e RESUME_API_TOKEN=<自定义> \
#          -e RESUME_CORS_ORIGINS=https://<你的前端域名> resume-producer-api

FROM python:3.12-slim-bookworm

# XeLaTeX + 依赖包（geometry/enumitem/hyperref 在 latex-recommended，tex-gyre 字体独立包）
RUN apt-get update && apt-get install -y --no-install-recommends \
        texlive-xetex texlive-latex-recommended tex-gyre fonts-texgyre \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev
COPY src ./src
COPY examples ./examples
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    RESUME_DATA_DIR=/app/data

VOLUME /app/data
EXPOSE 8000
CMD ["uvicorn", "resume_producer.api:app", "--host", "0.0.0.0", "--port", "8000"]
