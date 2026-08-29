# AI-DM 赛博跑团引擎 — 后端/核心服务镜像
FROM python:3.12-slim

WORKDIR /srv/ai-dm

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

# 依赖层(利用 Docker 缓存)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY app ./app
COPY static ./static
COPY eval ./eval
COPY .env.example ./.env.example

# 运行期数据目录(可挂载卷覆盖)
RUN mkdir -p data/sessions data/images

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]