SHELL=/usr/bin/env bash
# Makefile for ApollosAI project

# Variables
BACKEND_HOST ?= "127.0.0.1"
BACKEND_PORT ?= 3000
BACKEND_HOST_PORT = "$(BACKEND_HOST):$(BACKEND_PORT)"
FRONTEND_HOST ?= "127.0.0.1"
FRONTEND_PORT ?= 3001
DEFAULT_WORKSPACE_DIR = "./workspace"
DEFAULT_MODEL = "gpt-5-mini"
CONFIG_FILE = config.toml
PRE_COMMIT_CONFIG_PATH = "./dev_config/python/.pre-commit-config.yaml"
PYTHON_VERSION = 3.12
KIND_CLUSTER_NAME = "apollos-ai"

# ANSI color codes
GREEN=$(shell tput -Txterm setaf 2)
YELLOW=$(shell tput -Txterm setaf 3)
RED=$(shell tput -Txterm setaf 1)
BLUE=$(shell tput -Txterm setaf 6)
RESET=$(shell tput -Txterm sgr0)

# Build
build:
	@echo "$(GREEN)Building project...$(RESET)"
	@$(MAKE) -s check-dependencies
	@$(MAKE) -s install-python-dependencies
	@$(MAKE) -s install-frontend-dependencies
	@$(MAKE) -s install-pre-commit-hooks
	@$(MAKE) -s build-frontend
	@echo "$(GREEN)Build completed successfully.$(RESET)"

check-dependencies:
	@echo "$(YELLOW)Checking dependencies...$(RESET)"
	@$(MAKE) -s check-system
	@$(MAKE) -s check-python
	@$(MAKE) -s check-npm
	@$(MAKE) -s check-nodejs
ifeq ($(INSTALL_DOCKER),)
	@$(MAKE) -s check-docker
endif
	@$(MAKE) -s check-poetry
	@$(MAKE) -s check-tmux
	@echo "$(GREEN)Dependencies checked successfully.$(RESET)"

check-system:
	@echo "$(YELLOW)Checking system...$(RESET)"
	@if [ "$(shell uname)" = "Darwin" ]; then \
		echo "$(BLUE)macOS detected.$(RESET)"; \
	elif [ "$(shell uname)" = "Linux" ]; then \
		if [ -f "/etc/manjaro-release" ]; then \
			echo "$(BLUE)Manjaro Linux detected.$(RESET)"; \
		else \
			echo "$(BLUE)Linux detected.$(RESET)"; \
		fi; \
	elif [ "$$(uname -r | grep -i microsoft)" ]; then \
		echo "$(BLUE)Windows Subsystem for Linux detected.$(RESET)"; \
	else \
		echo "$(RED)Unsupported system detected. Please use macOS, Linux, or Windows Subsystem for Linux (WSL).$(RESET)"; \
		exit 1; \
	fi

check-python:
	@echo "$(YELLOW)Checking Python installation...$(RESET)"
	@if command -v python$(PYTHON_VERSION) > /dev/null; then \
		echo "$(BLUE)$(shell python$(PYTHON_VERSION) --version) is already installed.$(RESET)"; \
	else \
		echo "$(RED)Python $(PYTHON_VERSION) is not installed. Please install Python $(PYTHON_VERSION) to continue.$(RESET)"; \
		exit 1; \
	fi

check-npm:
	@echo "$(YELLOW)Checking npm installation...$(RESET)"
	@if command -v npm > /dev/null; then \
		echo "$(BLUE)npm $(shell npm --version) is already installed.$(RESET)"; \
	else \
		echo "$(RED)npm is not installed. Please install Node.js to continue.$(RESET)"; \
		exit 1; \
	fi

check-nodejs:
	@echo "$(YELLOW)Checking Node.js installation...$(RESET)"
	@if command -v node > /dev/null; then \
		NODE_VERSION=$(shell node --version | sed -E 's/v//g'); \
		IFS='.' read -r -a NODE_VERSION_ARRAY <<< "$$NODE_VERSION"; \
		if [ "$${NODE_VERSION_ARRAY[0]}" -ge 22 ]; then \
			echo "$(BLUE)Node.js $$NODE_VERSION is already installed.$(RESET)"; \
		else \
			echo "$(RED)Node.js 22.x or later is required. Please install Node.js 22.x or later to continue.$(RESET)"; \
			exit 1; \
		fi; \
	else \
		echo "$(RED)Node.js is not installed. Please install Node.js to continue.$(RESET)"; \
		exit 1; \
	fi

check-docker:
	@echo "$(YELLOW)Checking Docker installation...$(RESET)"
	@if command -v docker > /dev/null; then \
		echo "$(BLUE)$(shell docker --version) is already installed.$(RESET)"; \
	else \
		echo "$(RED)Docker is not installed. Please install Docker to continue.$(RESET)"; \
		exit 1; \
	fi

check-tmux:
	@echo "$(YELLOW)Checking tmux installation...$(RESET)"
	@if command -v tmux > /dev/null; then \
		echo "$(BLUE)$(shell tmux -V) is already installed.$(RESET)"; \
	else \
		echo "$(YELLOW)╔════════════════════════════════════════════════════════════════════════════╗$(RESET)"; \
		echo "$(YELLOW)║ OPTIONAL: tmux is not installed.                                          ║$(RESET)"; \
		echo "$(YELLOW)║ Some advanced terminal features may not work without tmux.                ║$(RESET)"; \
		echo "$(YELLOW)║ You can install it if needed, but it's not required for development.      ║$(RESET)"; \
		echo "$(YELLOW)╚════════════════════════════════════════════════════════════════════════════╝$(RESET)"; \
	fi

check-poetry:
	@echo "$(YELLOW)Checking Poetry installation...$(RESET)"
	@if command -v poetry > /dev/null; then \
		POETRY_VERSION=$(shell poetry --version 2>&1 | sed -E 's/Poetry \(version ([0-9]+\.[0-9]+\.[0-9]+)\)/\1/'); \
		IFS='.' read -r -a POETRY_VERSION_ARRAY <<< "$$POETRY_VERSION"; \
		if [ $${POETRY_VERSION_ARRAY[0]} -gt 1 ] || ([ $${POETRY_VERSION_ARRAY[0]} -eq 1 ] && [ $${POETRY_VERSION_ARRAY[1]} -ge 8 ]); then \
			echo "$(BLUE)$(shell poetry --version) is already installed.$(RESET)"; \
		else \
			echo "$(RED)Poetry 1.8 or later is required. You can install poetry by running the following command, then adding Poetry to your PATH:"; \
			echo "$(RED) curl -sSL https://install.python-poetry.org | python$(PYTHON_VERSION) -$(RESET)"; \
			echo "$(RED)More detail here: https://python-poetry.org/docs/#installing-with-the-official-installer$(RESET)"; \
			exit 1; \
		fi; \
	else \
		echo "$(RED)Poetry is not installed. You can install poetry by running the following command, then adding Poetry to your PATH:"; \
		echo "$(RED) curl -sSL https://install.python-poetry.org | python$(PYTHON_VERSION) -$(RESET)"; \
		echo "$(RED)More detail here: https://python-poetry.org/docs/#installing-with-the-official-installer$(RESET)"; \
		exit 1; \
	fi

install-python-dependencies:
	@echo "$(GREEN)Installing Python dependencies...$(RESET)"
	@if [ -z "${TZ}" ]; then \
		echo "Defaulting TZ (timezone) to UTC"; \
		export TZ="UTC"; \
	fi
	poetry env use python$(PYTHON_VERSION)
	@if [ "$(shell uname)" = "Darwin" ]; then \
		echo "$(BLUE)Installing chroma-hnswlib...$(RESET)"; \
		export HNSWLIB_NO_NATIVE=1; \
		poetry run pip install chroma-hnswlib; \
	fi
	@if [ -n "${POETRY_GROUP}" ]; then \
		echo "Installing only POETRY_GROUP=${POETRY_GROUP}"; \
		poetry install --only $${POETRY_GROUP}; \
	else \
		poetry install --with dev,test,runtime; \
	fi
	@if [ "${INSTALL_PLAYWRIGHT}" != "false" ] && [ "${INSTALL_PLAYWRIGHT}" != "0" ]; then \
		if [ -f "/etc/manjaro-release" ]; then \
			echo "$(BLUE)Detected Manjaro Linux. Installing Playwright dependencies...$(RESET)"; \
			poetry run pip install playwright; \
			poetry run playwright install chromium; \
		else \
			if [ ! -f cache/playwright_chromium_is_installed.txt ]; then \
				echo "Running playwright install --with-deps chromium..."; \
				poetry run playwright install --with-deps chromium; \
				mkdir -p cache; \
				touch cache/playwright_chromium_is_installed.txt; \
			else \
				echo "Setup already done. Skipping playwright installation."; \
			fi \
		fi \
	else \
		echo "Skipping Playwright installation (INSTALL_PLAYWRIGHT=${INSTALL_PLAYWRIGHT})."; \
	fi
	@echo "$(GREEN)Python dependencies installed successfully.$(RESET)"

install-frontend-dependencies: check-npm check-nodejs
	@echo "$(YELLOW)Setting up frontend environment...$(RESET)"
	@echo "$(YELLOW)Detect Node.js version...$(RESET)"
	@cd frontend && node ./scripts/detect-node-version.js
	echo "$(BLUE)Installing frontend dependencies with npm...$(RESET)"
	@cd frontend && npm install
	@echo "$(GREEN)Frontend dependencies installed successfully.$(RESET)"

install-pre-commit-hooks: check-python check-poetry install-python-dependencies
	@echo "$(YELLOW)Installing pre-commit hooks...$(RESET)"
	@git config --unset-all core.hooksPath || true
	@poetry run pre-commit install --config $(PRE_COMMIT_CONFIG_PATH)
	@echo "$(GREEN)Pre-commit hooks installed successfully.$(RESET)"

lint-backend: install-pre-commit-hooks
	@echo "$(YELLOW)Running linters...$(RESET)"
	@poetry run pre-commit run --all-files --show-diff-on-failure --config $(PRE_COMMIT_CONFIG_PATH)

lint-frontend: install-frontend-dependencies
	@echo "$(YELLOW)Running linters for frontend...$(RESET)"
	@cd frontend && npm run lint

lint:
	@$(MAKE) -s lint-frontend
	@$(MAKE) -s lint-backend

kind:
	@echo "$(YELLOW)Checking if kind is installed...$(RESET)"
	@if ! command -v kind > /dev/null; then \
		echo "$(RED)kind is not installed. Please install kind with `brew install kind` to continue$(RESET)"; \
		exit 1; \
	else \
		echo "$(BLUE)kind $(shell kind version) is already installed.$(RESET)"; \
	fi
	@echo "$(YELLOW)Checking if kind cluster '$(KIND_CLUSTER_NAME)' already exists...$(RESET)"
	@if kind get clusters | grep -q "^$(KIND_CLUSTER_NAME)$$"; then \
		echo "$(BLUE)Kind cluster '$(KIND_CLUSTER_NAME)' already exists.$(RESET)"; \
		kubectl config use-context kind-$(KIND_CLUSTER_NAME); \
	else \
		echo "$(YELLOW)Creating kind cluster '$(KIND_CLUSTER_NAME)'...$(RESET)"; \
		kind create cluster --name $(KIND_CLUSTER_NAME) --config kind/cluster.yaml; \
	fi
	@echo "$(YELLOW)Checking if mirrord is installed...$(RESET)"
	@if ! command -v mirrord > /dev/null; then \
		echo "$(RED)mirrord is not installed. Please install mirrord with `brew install metalbear-co/mirrord/mirrord` to continue$(RESET)"; \
		exit 1; \
	else \
		echo "$(BLUE)mirrord $(shell mirrord --version) is already installed.$(RESET)"; \
	fi
	@echo "$(YELLOW)Installing k8s mirrord resources...$(RESET)"
	@kubectl apply -f kind/manifests
	@echo "$(GREEN)Mirrord resources installed successfully.$(RESET)"
	@echo "$(YELLOW)Waiting for Mirrord pod to be ready.$(RESET)"
	@sleep 5
	@kubectl wait --for=condition=Available deployment/ubuntu-dev
	@echo "$(YELLOW)Waiting for Nginx to be ready.$(RESET)"
	@kubectl -n ingress-nginx wait --for=condition=Available deployment/ingress-nginx-controller
	@echo "$(YELLOW)Running make run inside of mirrord.$(RESET)"
	@mirrord exec --target deployment/ubuntu-dev -- make run

test-apollosai:
	@echo "$(YELLOW)Running ApollosAI unit tests...$(RESET)"
	@poetry run pytest tests/unit/apollosai/ -v

test-apollosai-cov:
	@echo "$(YELLOW)Running ApollosAI tests with coverage...$(RESET)"
	@poetry run pytest tests/unit/apollosai/ --cov=apollosai --cov-branch --cov-report=term-missing

test-backend:
	@echo "$(YELLOW)Running all backend unit tests...$(RESET)"
	@poetry run pytest tests/unit/ --forked -n auto

test-frontend:
	@echo "$(YELLOW)Running tests for frontend...$(RESET)"
	@cd frontend && npm run test

test:
	@$(MAKE) -s test-apollosai
	@$(MAKE) -s test-frontend

build-frontend:
	@echo "$(YELLOW)Building frontend...$(RESET)"
	@cd frontend && npm run prepare && npm run build

# Start ApollosAI backend (primary development target)
start-apollosai: check-env
	@echo "$(YELLOW)Starting ApollosAI backend...$(RESET)"
	@poetry run uvicorn apollosai.app_server:app --host $(BACKEND_HOST) --port $(BACKEND_PORT) \
		--reload --reload-dir ./apollosai --reload-dir ./openhands --reload-exclude "./workspace"

# Start OpenHands V0 backend (legacy — deprecated April 2026)
start-backend:
	@echo "$(YELLOW)Starting OpenHands V0 backend (legacy)...$(RESET)"
	@poetry run uvicorn openhands.server.listen:app --host $(BACKEND_HOST) --port $(BACKEND_PORT) --reload --reload-exclude "./workspace"

# Start frontend
start-frontend:
	@echo "$(YELLOW)Starting frontend...$(RESET)"
	@cd frontend && \
	if grep -qi microsoft /proc/version 2>/dev/null; then \
		echo "Detected WSL environment. Using 'dev_wsl'"; \
		SCRIPT=dev_wsl; \
	else \
		SCRIPT=dev; \
	fi; \
	VITE_BACKEND_HOST=$(BACKEND_HOST_PORT) VITE_FRONTEND_PORT=$(FRONTEND_PORT) npm run $$SCRIPT -- --port $(FRONTEND_PORT) --host $(BACKEND_HOST)

# Common setup for running the app (non-callable)
_run_setup: check-env
	@if [ "$(OS)" = "Windows_NT" ]; then \
		echo "$(RED) Windows is not supported, use WSL instead!$(RESET)"; \
		exit 1; \
	fi
	@mkdir -p logs
	@echo "$(YELLOW)Starting ApollosAI backend server...$(RESET)"
	@poetry run uvicorn apollosai.app_server:app --host $(BACKEND_HOST) --port $(BACKEND_PORT) &
	@echo "$(YELLOW)Waiting for the backend to start...$(RESET)"
	@until nc -z localhost $(BACKEND_PORT); do sleep 0.1; done
	@echo "$(GREEN)Backend started successfully.$(RESET)"

# Run the app (standard mode)
run:
	@echo "$(YELLOW)Running the app...$(RESET)"
	@$(MAKE) -s _run_setup
	@$(MAKE) -s start-frontend
	@echo "$(GREEN)Application started successfully.$(RESET)"

# Run the app (in docker)
docker-run: WORKSPACE_BASE ?= $(PWD)/workspace
docker-run:
	@if [ -f /.dockerenv ]; then \
		echo "Running inside a Docker container. Exiting..."; \
		exit 0; \
	else \
		echo "$(YELLOW)Running the app in Docker $(OPTIONS)...$(RESET)"; \
		export WORKSPACE_BASE=${WORKSPACE_BASE}; \
		export SANDBOX_USER_ID=$(shell id -u); \
		export DATE=$(shell date +%Y%m%d%H%M%S); \
		docker compose up $(OPTIONS); \
	fi


# Setup config.toml
setup-config:
	@echo "$(YELLOW)Setting up config.toml...$(RESET)"
	@$(MAKE) setup-config-prompts
	@mv $(CONFIG_FILE).tmp $(CONFIG_FILE)
	@echo "$(GREEN)Config.toml setup completed.$(RESET)"

setup-config-prompts:
	@echo "[core]" > $(CONFIG_FILE).tmp

	@read -p "Enter your workspace directory (as absolute path) [default: $(DEFAULT_WORKSPACE_DIR)]: " workspace_dir; \
	 workspace_dir=$${workspace_dir:-$(DEFAULT_WORKSPACE_DIR)}; \
	 echo "workspace_base=\"$$workspace_dir\"" >> $(CONFIG_FILE).tmp

	@echo "" >> $(CONFIG_FILE).tmp

	@echo "[llm]" >> $(CONFIG_FILE).tmp
	@read -p "Enter your LLM model name, used for running without UI. Set the model in the UI after you start the app. (see https://docs.litellm.ai/docs/providers for full list) [default: $(DEFAULT_MODEL)]: " llm_model; \
	 llm_model=$${llm_model:-$(DEFAULT_MODEL)}; \
	 echo "model=\"$$llm_model\"" >> $(CONFIG_FILE).tmp

	@read -p "Enter your LLM api key: " llm_api_key; \
	 echo "api_key=\"$$llm_api_key\"" >> $(CONFIG_FILE).tmp

	@read -p "Enter your LLM base URL [mostly used for local LLMs, leave blank if not needed - example: http://localhost:5001/v1/]: " llm_base_url; \
	 if [[ ! -z "$$llm_base_url" ]]; then echo "base_url=\"$$llm_base_url\"" >> $(CONFIG_FILE).tmp; fi

setup-config-basic:
	@printf '%s\n' \
	'[core]' \
	'workspace_base="./workspace"' \
	> config.toml
	@echo "$(GREEN)config.toml created.$(RESET)"

# Validate .env exists (prerequisite for ApollosAI targets)
check-env:
	@if [ ! -f .env ]; then \
		echo "$(RED).env file not found. Run 'make setup-env' first.$(RESET)"; \
		exit 1; \
	fi

# Bootstrap .env from .env.example
setup-env:
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creating .env from .env.example...$(RESET)"; \
		cp .env.example .env; \
		echo "$(GREEN).env created. Edit it with your configuration.$(RESET)"; \
	else \
		echo "$(BLUE).env already exists. Skipping.$(RESET)"; \
	fi

# Database migrations (requires DATABASE_URL — set in .env or environment)
migrate: check-env
	@echo "$(YELLOW)Running ApollosAI database migrations...$(RESET)"
	@PYTHONPATH=".:$$PYTHONPATH" poetry run alembic -c apollosai/alembic.ini upgrade head
	@echo "$(GREEN)Migrations complete.$(RESET)"

migrate-create: check-env
	@if [ -z "$(MSG)" ]; then \
		echo "$(RED)Usage: make migrate-create MSG='description of migration'$(RESET)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Creating new migration...$(RESET)"
	@PYTHONPATH=".:$$PYTHONPATH" poetry run alembic -c apollosai/alembic.ini revision --autogenerate -m "$(MSG)"
	@echo "$(YELLOW)Migration created. Run pre-commit --all-files to fix ruff formatting, then re-stage.$(RESET)"

migrate-status: check-env
	@echo "$(YELLOW)Checking migration status...$(RESET)"
	@PYTHONPATH=".:$$PYTHONPATH" poetry run alembic -c apollosai/alembic.ini current

# Self-hosted development mode (all interfaces exposed)
dev-exposed:
	@$(MAKE) run BACKEND_HOST="0.0.0.0" BACKEND_PORT="12000" FRONTEND_HOST="0.0.0.0" FRONTEND_PORT="12001"

# Docker builds
docker-build-app:
	@echo "$(YELLOW)Building ApollosAI app image...$(RESET)"
	@./containers/build.sh -i openhands --load

docker-build-ent:
	@echo "$(YELLOW)Building ApollosAI enterprise image...$(RESET)"
	@./containers/build.sh -i apollosai --load

# Develop in container
docker-dev:
	@if [ -f /.dockerenv ]; then \
		echo "Running inside a Docker container. Exiting..."; \
		exit 0; \
	else \
		echo "$(YELLOW)Build and run in Docker $(OPTIONS)...$(RESET)"; \
		./containers/dev/dev.sh $(OPTIONS); \
	fi

# Clean up all caches
clean:
	@echo "$(YELLOW)Cleaning up caches...$(RESET)"
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -rf openhands/.cache .mypy_cache .ruff_cache .pytest_cache
	@echo "$(GREEN)Caches cleaned up successfully.$(RESET)"

# Help
help:
	@echo "$(BLUE)Usage: make [target]$(RESET)"
	@echo ""
	@echo "$(YELLOW)Core:$(RESET)"
	@echo "  $(GREEN)build$(RESET)               - Build project (Python deps, frontend, pre-commit hooks)"
	@echo "  $(GREEN)run$(RESET)                 - Run ApollosAI (backend + frontend)"
	@echo "  $(GREEN)start-apollosai$(RESET)     - Start ApollosAI backend server"
	@echo "  $(GREEN)start-backend$(RESET)       - Start OpenHands V0 backend (legacy)"
	@echo "  $(GREEN)start-frontend$(RESET)      - Start frontend dev server"
	@echo ""
	@echo "$(YELLOW)Database:$(RESET)"
	@echo "  $(GREEN)migrate$(RESET)             - Run ApollosAI Alembic migrations"
	@echo "  $(GREEN)migrate-create$(RESET)      - Create new migration (MSG='description')"
	@echo "  $(GREEN)migrate-status$(RESET)      - Check current migration status"
	@echo ""
	@echo "$(YELLOW)Testing:$(RESET)"
	@echo "  $(GREEN)test$(RESET)                - Run ApollosAI unit tests + frontend tests"
	@echo "  $(GREEN)test-apollosai$(RESET)      - Run ApollosAI unit tests"
	@echo "  $(GREEN)test-apollosai-cov$(RESET)  - Run ApollosAI tests with coverage"
	@echo "  $(GREEN)test-backend$(RESET)        - Run all backend unit tests"
	@echo "  $(GREEN)test-frontend$(RESET)       - Run frontend tests"
	@echo ""
	@echo "$(YELLOW)Linting:$(RESET)"
	@echo "  $(GREEN)lint$(RESET)                - Run all linters (backend + frontend)"
	@echo "  $(GREEN)lint-backend$(RESET)        - Run Python linters (pre-commit)"
	@echo "  $(GREEN)lint-frontend$(RESET)       - Run frontend linters"
	@echo ""
	@echo "$(YELLOW)Docker:$(RESET)"
	@echo "  $(GREEN)docker-build-app$(RESET)    - Build ApollosAI app Docker image"
	@echo "  $(GREEN)docker-build-ent$(RESET)    - Build ApollosAI enterprise Docker image"
	@echo "  $(GREEN)docker-run$(RESET)          - Run ApollosAI via Docker Compose"
	@echo "  $(GREEN)docker-dev$(RESET)          - Develop inside Docker container"
	@echo ""
	@echo "$(YELLOW)Config:$(RESET)"
	@echo "  $(GREEN)setup-config$(RESET)        - Interactive LLM config setup (config.toml)"
	@echo "  $(GREEN)setup-env$(RESET)           - Bootstrap .env from .env.example"
	@echo "  $(GREEN)clean$(RESET)               - Clean build artifacts and caches"
	@echo "  $(GREEN)help$(RESET)                - Display this help message"

# Phony targets
.PHONY: build check-dependencies check-system check-python check-npm check-nodejs check-docker check-tmux check-poetry
.PHONY: install-python-dependencies install-frontend-dependencies install-pre-commit-hooks
.PHONY: lint-backend lint-frontend lint
.PHONY: start-apollosai start-backend start-frontend _run_setup run dev-exposed
.PHONY: check-env setup-env setup-config setup-config-prompts setup-config-basic
.PHONY: migrate migrate-create migrate-status
.PHONY: test-apollosai test-apollosai-cov test-backend test-frontend test
.PHONY: docker-build-app docker-build-ent docker-run docker-dev
.PHONY: build-frontend clean help kind
