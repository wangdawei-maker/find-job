# 阿里云制品中心基础镜像，避免从 Docker Hub 拉取超时（ECS 上更易拉取）
FROM alibaba-cloud-linux-3-registry.cn-hangzhou.cr.aliyuncs.com/alinux3/python:3.11.1

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# PyPI 官方源在部分 ECS 上访问 files.pythonhosted.org 易超时，改用阿里云镜像
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_TRUSTED_HOST=mirrors.aliyun.com

COPY requirements.txt ./
RUN pip install --no-cache-dir --default-timeout=120 -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
