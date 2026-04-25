# ============================================
# SmartInventory Frontend - Multi-stage Dockerfile
# ============================================

# Stage 1: Base
FROM node:18-alpine AS base
WORKDIR /app
ENV PATH /app/node_modules/.bin:$PATH

# Stage 2: Dependencies
FROM base AS dependencies
COPY package.json package-lock.json ./
RUN npm ci --silent

# Stage 3: Development
FROM dependencies AS development
COPY . .
EXPOSE 3000
CMD ["npm", "start"]

# Stage 4: Build
FROM dependencies AS build
COPY . .
RUN npm run build

# Stage 5: Production
FROM nginx:alpine AS production

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built app
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
