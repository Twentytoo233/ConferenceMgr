FROM node:18

# 设置工作目录
WORKDIR /app

# 安装依赖并构建
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# 使用 nginx 作为生产环境服务器（可选）
FROM nginx:stable-alpine
COPY --from=0 /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
