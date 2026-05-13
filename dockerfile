FROM python:3.11.15-trixie AS builder

## 不要修改 WORKDIR ！
WORKDIR /app 
# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/


COPY pyproject.toml uv.lock* /app

# 安装依赖（生产环境，不安装 dev 组）
RUN uv sync --frozen --no-dev --no-install-project

# 最终运行阶段（多阶段构建，镜像更小）
FROM python:3.11.15-trixie

## 不要修改 WORKDIR ！
WORKDIR /app 

# 从 builder 阶段复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 关键：把 uv 也复制进来（解决 uv not found）
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/bin/uvx /usr/local/bin/uvx

ENV PATH="/app/.venv/bin:$PATH"
ENV UV_LINK_MODE=copy

# 复制项目代码
COPY src/ /app/src/
COPY entrypoint.sh /app/entrypoint.sh
COPY .env.prod /app/.env

# 确保 entrypoint 可执行
RUN chmod +x /app/entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["/app/entrypoint.sh"]