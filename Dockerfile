# 1. 基础镜像：使用轻量级 Python
FROM python:3.9-alpine

# 2. 添加元数据
LABEL maintainer="Suyurine <info@suyuri.com>"
LABEL version="1.0.0"
LABEL description="Auto sync Obsidian Livesync(CouchDB) to local Markdown files"

# 3. 设置工作目录
WORKDIR /app

# 4. 安装依赖
# 将 requirements.txt 单独复制，利用 Docker 缓存机制加速构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 复制源代码
COPY main.py .

# 6. 环境变量设置
# 禁用 Python 缓冲，确保日志实时输出到 Docker logs
ENV PYTHONUNBUFFERED=1
# 设置默认时区 (可选，方便日志查看)
ENV TZ=Asia/Shanghai

# 7. 启动命令
CMD ["python", "main.py"]