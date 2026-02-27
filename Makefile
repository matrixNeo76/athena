# ATHENA — Developer convenience commands
# Prerequisites: Docker, Python 3.11+, Node 20+, npm
# Run `make help` for a description of all targets.

.PHONY: help dev dev-stub dev-down dev-logs \
        test test-backend test-frontend lint \
        build clean install

BACKEND_DIR := backend
FRONTEND_DIR := frontend

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  ATHENA — Autonomous Multi-Agent Intelligence Platform"
	@echo "  ─────────────────────────────────────────────────────────────"
	@echo ""
	@echo "  DOCKER COMPOSE"
	@echo "  make dev             Start full stack (needs credentials in .env)"
	@echo "  make dev-stub        Start in stub/demo mode (no credentials needed)"
	@echo "  make dev-down        Stop and remove containers"
	@echo "  make dev-logs        Tail all container logs"
	@echo ""
	@echo "  TESTING"
	@echo "  make test            Run all tests (backend + frontend)"
	@echo "  make test-backend    Run Python pytest suite (~167 tests)"
	@echo "  make test-frontend   Run TypeScript type check + ESLint"
	@echo "  make lint            Alias for test-frontend"
	@echo ""
	@echo "  SETUP & BUILD"
	@echo "  make install         Install all local dependencies"
	@echo "  make build           Build Docker images (no start)"
	@echo "  make clean           Stop containers, remove volumes & build artefacts"
	@echo ""

# ── Docker Compose ────────────────────────────────────────────────────────────
dev:
	docker compose up --build

dev-stub:
	STUB_MODE=true docker compose up --build

dev-down:
	docker compose down

dev-logs:
	docker compose logs -f

# ── Local install ──────────────────────────────────────────────────────────────
install:
	@echo "── Installing backend dependencies ────────────────────────────────"
	cd $(BACKEND_DIR) && pip install -r requirements.txt
	@echo "── Installing frontend dependencies ───────────────────────────────"
	cd $(FRONTEND_DIR) && npm ci
	@echo ""
	@echo "  Copy and configure .env files:"
	@echo "      cp backend/.env.example backend/.env"
	@echo "      cp frontend/.env.local.example frontend/.env.local"
	@echo ""

# ── Testing ─────────────────────────────────────────────────────────────────────
test: test-backend test-frontend
	@echo ""
	@echo "  All checks passed"

test-backend:
	@echo "── Backend tests (pytest) ──────────────────────────────────────────────"
	cd $(BACKEND_DIR) && \
	  STUB_MODE=true \
	  DEPLOY_AI_CLIENT_ID="" \
	  pytest tests/ -v --tb=short

test-frontend:
	@echo "── Frontend checks (TypeScript + ESLint) ────────────────────────────"
	cd $(FRONTEND_DIR) && npx tsc --noEmit
	cd $(FRONTEND_DIR) && npm run lint

lint: test-frontend

# ── Build & Clean ──────────────────────────────────────────────────────────────
build:
	docker compose build

clean:
	docker compose down -v
	rm -rf $(FRONTEND_DIR)/.next
	rm -rf $(BACKEND_DIR)/.pytest_cache
	rm -rf $(BACKEND_DIR)/reports
	find . -type d -name __pycache__   -exec rm -rf {} + 2>/dev/null || true
	@echo "  Clean complete"
