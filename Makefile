.PHONY: install dev mcp server functions funcvenv test test-e2e clean azurite-up azurite-down reset up

install:
	uv sync
	npm install

azurite-up:
	docker compose up -d azurite

azurite-down:
	docker compose down

reset:
	docker compose stop azurite
	rm -rf azurite-data/*
	docker compose up -d azurite
	@echo "azurite reset — restart func + uvicorn to clear in-memory state"

mcp:
	npm run dev:mcp

server:
	uv run uvicorn api.server.main:app --port 3001 --reload

# One-time setup: create a Python 3.11 venv for Azure Functions Core Tools.
# Core Tools bundles Python 3.11; our main uv venv is Python 3.13 (incompatible C extensions).
# Run once: make funcvenv
funcvenv:
	py -3.11 -m venv .funcvenv
	.funcvenv/Scripts/pip install -r requirements.txt --quiet

# Start Azure Functions host.
# Prerequisites: make funcvenv && make azurite-up
# On Windows activate .funcvenv first, then run this target.
# NOTE: requires Core Tools v4.0.6000+ (ships .NET 8) for Durable extension bundle v4.
#       Update: npm install -g azure-functions-core-tools@4 --unsafe-perm true
functions:
	source .funcvenv/Scripts/activate && PYTHONPATH="$$(pwd)" func start --port 7071

dev: azurite-up
	@echo "Start in 3 terminals: 'make mcp' / 'make server' / 'make functions'"

# One command to boot the entire stack (azurite + mocks + func + fastapi + vite).
# Ctrl-C stops everything.
up:
	bash scripts/boot-demo.sh

test:
	uv run pytest -q
	npm test --silent

# Playwright — requires the stack to already be running (`make up` in another terminal).
test-e2e:
	npx playwright test --reporter=list

clean:
	docker compose down -v
	rm -rf .venv .funcvenv .python_packages node_modules dist __pycache__ .pytest_cache .ruff_cache azurite-data test-results
