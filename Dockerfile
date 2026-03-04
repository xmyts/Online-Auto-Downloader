FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖和 ffmpeg (兼容 ARM64 和 AMD64)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 设置时区为亚洲/上海
ENV TZ=Asia/Shanghai

# 复制依赖列表并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目全部代码
COPY . .

# 暴露 Gradio 的默认端口
EXPOSE 7860

# 启动命令
CMD ["python", "main.py"]