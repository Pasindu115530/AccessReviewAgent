FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install --no-audit --no-fund
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine
RUN apk add --no-cache gettext ca-certificates
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/conf.d/accessreview.template
COPY start.sh /start.sh
RUN chmod +x /start.sh
ENV API_UPSTREAM=host.pasinduudana.me
EXPOSE 80
ENTRYPOINT ["/start.sh"]
