# real-time-service/Dockerfile

# ---- Base Stage ----
# Establishes our base environment with Node.js and pnpm
FROM node:18-alpine AS base
WORKDIR /usr/src/app
RUN npm install -g pnpm

# ---- Builder Stage ----
# This stage installs ALL dependencies and builds the application.
FROM base AS builder
COPY package.json pnpm-lock.yaml ./
# ✅ REMOVED the --prod flag to install devDependencies like Prisma
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm prisma generate
RUN pnpm run build

# ---- Runner Stage (Final Image) ----
# This is the final, optimized image that will run in production.
FROM base AS runner
COPY package.json pnpm-lock.yaml ./
# ✅ Here, we ONLY install production dependencies to keep the image small.
RUN pnpm install --frozen-lockfile --prod
# Copy the built application and prisma schema from the builder stage
COPY --from=builder /usr/src/app/dist ./dist
COPY prisma ./prisma

# The command to start the application
CMD ["node", "dist/main"]