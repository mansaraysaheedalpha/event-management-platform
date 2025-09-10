# apollo-gateway/Dockerfile

# ---- Base Stage: Install dependencies ----
# Using a specific version for consistency
FROM node:18-alpine AS base
WORKDIR /usr/src/app
# Copy package files and install dependencies with pnpm
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm
RUN pnpm install --frozen-lockfile

# ---- Build Stage: Compile TypeScript to JavaScript ----
FROM base AS build
# Copy the rest of the source code
COPY . .
# Run the build script defined in your package.json
RUN pnpm run build

# ---- Production Stage: Create the final, small image ----
FROM node:18-alpine AS production
WORKDIR /usr/src/app

# Copy only the necessary files from the previous stages
COPY --from=build /usr/src/app/dist ./dist
COPY --from=build /usr/src/app/node_modules ./node_modules
COPY --from=build /usr/src/app/package.json ./package.json

# Expose the port the gateway will run on
EXPOSE 4000

# The command to start the application
CMD ["node", "dist/index.js"]