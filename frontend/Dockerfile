FROM node:24-alpine AS base

WORKDIR /app

RUN apk add --no-cache libc6-compat

ARG PNPM_VERSION=10.30.1
RUN corepack enable && corepack prepare pnpm@${PNPM_VERSION} --activate

FROM base AS deps

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS build

ARG VITE_API_URL=http://localhost:8100
ENV VITE_API_URL=${VITE_API_URL}

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN pnpm build

FROM node:24-alpine AS runner

RUN apk add --no-cache curl

WORKDIR /app

COPY deploy/server.mjs ./server.mjs
COPY --from=build /app/dist ./dist

EXPOSE 3100

CMD ["node", "server.mjs"]
