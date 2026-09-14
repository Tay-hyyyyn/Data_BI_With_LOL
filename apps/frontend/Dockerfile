FROM node:22-alpine AS build
WORKDIR /web
COPY apps/frontend/package.json apps/frontend/pnpm-lock.yaml* ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY apps/frontend ./
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=build /web/dist /usr/share/nginx/html
COPY infra/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
