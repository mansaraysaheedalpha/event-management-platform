# ---- Base Stage ----
FROM node:18-alpine AS base
WORKDIR /usr/src/app
# Use pnpm as the package manager
RUN npm install -g pnpm

# ---- Dependencies Stage ----
FROM base AS deps
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --prod

# ---- Builder Stage ----
FROM base AS builder
COPY --from=deps /usr/src/app/node_modules ./node_modules
COPY . .
# Generate Prisma Client
RUN pnpm prisma generate
# Build the application
RUN pnpm run build

# ---- Runner Stage (Final Image) ----
FROM base AS runner
COPY --from=deps /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app/dist ./dist
COPY prisma ./prisma

# The command to start the application
CMD ["node", "dist/main"]