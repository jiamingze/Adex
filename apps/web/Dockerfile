FROM node:22-alpine AS build
WORKDIR /src
RUN corepack enable && corepack prepare pnpm@10.11.0 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web apps/web
COPY packages/ui-web packages/ui-web
COPY packages/contracts packages/contracts
RUN --mount=type=cache,id=adex-pnpm,target=/pnpm/store pnpm install --store-dir /pnpm/store --frozen-lockfile && pnpm generate:contracts && pnpm --dir apps/web build
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/apps/web/dist /usr/share/nginx/html
