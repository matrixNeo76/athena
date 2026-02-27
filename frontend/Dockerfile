# ── ATHENA Frontend — Docker image (3-stage build) ────────────────────────────────────────────
#
# next.config.js sets output: 'standalone', which generates a self-contained
# server in .next/standalone/ requiring no full node_modules at runtime.
# Stage 3 uses this output for a minimal, production-optimised image.

# Stage 1: Install ALL dependencies (devDeps required by TypeScript build)
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# Stage 2: Build application
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* vars are baked into the client bundle at build time
ARG  NEXT_PUBLIC_API_URL=http://localhost:8000
ENV  NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
# Disable telemetry in CI / build environments
ENV  NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# Stage 3: Runtime — standalone output (minimal image, no full node_modules)
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Run as non-root user (container security best practice)
RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Standalone server + static assets + public directory
# .next/standalone contains server.js + a minimal node_modules subset
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone  ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static      ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public            ./public

USER nextjs

EXPOSE 3000
ENV  PORT=3000
ENV  HOSTNAME=0.0.0.0

# Health check: verify Next.js is serving the root page
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1

# Standalone entry point — does NOT require `npm start` or next binary
CMD ["node", "server.js"]
