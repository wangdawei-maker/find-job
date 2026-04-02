# 与后端一致：基础镜像走阿里云制品仓库；Node/Nginx 不依赖 Docker Hub
FROM alibaba-cloud-linux-3-registry.cn-hangzhou.cr.aliyuncs.com/alinux3/alinux3:220901.1 AS builder

WORKDIR /app

# Node 20 二进制来自 npmmirror（国内可达），避免 node:20-alpine 走 registry-1.docker.io
ENV NODE_VERSION=20.18.1
RUN dnf install -y ca-certificates curl tar xz gzip \
    && curl -fsSL "https://npmmirror.com/mirrors/node/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    | tar -xJ -C /usr/local --strip-components=1 \
    && dnf clean all

RUN npm config set registry https://registry.npmmirror.com

COPY package*.json ./
RUN npm ci

COPY . .
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM alibaba-cloud-linux-3-registry.cn-hangzhou.cr.aliyuncs.com/alinux3/alinux3:220901.1

RUN dnf install -y nginx \
    && dnf clean all \
    && rm -rf /var/cache/dnf

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
