# =============================================================================
# Stage 1: Build the React/Vite application
# =============================================================================
# Bookworm (not Alpine): corporate networks often block dl-cdn.alpinelinux.org (apk 403).
FROM node:20-bookworm-slim AS builder


# Set working directory
WORKDIR /app

# git required by webcrypto-liner-shim (proxy handles HTTP; HTTPS CONNECT is blocked by corporate Squid)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy package files first (better caching)
COPY package.json package-lock.json ./

# Install dependencies (npm install so package.json is enough; no lock file sync required)
RUN npm install

# Copy source code
COPY . .

# Build arguments — static across all environments (relative paths)
ARG VITE_LANGGRAPH_API_URL=/langgraph-api
ARG VITE_DOWNLOAD_SERVICE_API_URL=/download-api
ARG VITE_ACSS_API_URL=/acss-api
ARG VITE_ACSS_HEALTH_INTERVAL=5000
ARG VITE_KEYCLOAK_REALM=aan
ARG VITE_KEYCLOAK_CLIENT_ID=react-app-prod
ARG VITE_RAG_DOCUMENTATIONS_BASE_URL=teoco_data_store/document_rag/data
ARG VITE_RAG_IMAGES_BASE_URL=teoco_data_store/document_rag
# VITE_KEYCLOAK_URL intentionally omitted — injected at container startup

ENV VITE_LANGGRAPH_API_URL=$VITE_LANGGRAPH_API_URL
ENV VITE_DOWNLOAD_SERVICE_API_URL=$VITE_DOWNLOAD_SERVICE_API_URL
ENV VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM
ENV VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID
ENV VITE_ACSS_API_URL=$VITE_ACSS_API_URL
ENV VITE_ACSS_HEALTH_INTERVAL=$VITE_ACSS_HEALTH_INTERVAL
ENV VITE_RAG_DOCUMENTATIONS_BASE_URL=$VITE_RAG_DOCUMENTATIONS_BASE_URL
ENV VITE_RAG_IMAGES_BASE_URL=$VITE_RAG_IMAGES_BASE_URL

RUN npm run build

# =============================================================================
# Stage 2: Serve with Nginx
# =============================================================================
FROM nginx:alpine AS production

# Copy nginx config
COPY ./nginx.conf /etc/nginx/conf.d/default.conf

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Entrypoint generates /usr/share/nginx/html/env-config.js at startup
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

EXPOSE 80
EXPOSE 443

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
