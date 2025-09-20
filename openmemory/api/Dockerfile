FROM python:3.12-slim

LABEL org.opencontainers.image.name="mem0/openmemory-mcp"

# 接收从docker-compose传递的PIP镜像参数，默认使用清华镜像
ARG PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple

# 设置pip镜像源并信任该源
ENV PIP_INDEX_URL=${PIP_MIRROR}
ENV PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

WORKDIR /usr/src/openmemory

# 先升级pip到最新版本，提升依赖解析效率
RUN pip install --upgrade pip

# 复制依赖文件并安装（使用国内镜像加速）
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制项目其他文件
COPY config.json .
COPY . .

EXPOSE 8765
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]
