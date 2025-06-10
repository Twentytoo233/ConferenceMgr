FROM python:3.12-slim

# 系统依赖（OpenCV 需要）
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 ffmpeg \
    && apt-get clean

# 设置工作目录
WORKDIR /app

# 拷贝依赖并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝应用代码
COPY . .

# 默认启动
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
