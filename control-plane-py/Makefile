.PHONY: install dev mcp server functions funcvenv test clean azurite-up azurite-down

install:
	uv sync

azurite-up:
	docker compose up -d azurite

azurite-down:
	docker compose down

mcp:
	cd "../control-plane" && npm run dev:mcp

server:
	uv run uvicorn src.server.main:app --port 3001 --reload

# One-time setup: create a Python 3.11 venv for Azure Functions Core Tools.
# Core Tools bundles Python 3.11; our main uv venv is Python 3.13 (incompatible C extensions).
# Run once: make funcvenv
funcvenv:
	py -3.11 -m venv .funcvenv
	.funcvenv/Scripts/pip install -r requirements.txt --quiet

# Start Azure Functions host.
# Prerequisites: make funcvenv && make azurite-up
# On Windows activate .funcvenv first, then run this target, or run manually:
#   source .funcvenv/Scripts/activate && PYTHONPATH=$(pwd) func start --port 7071
# NOTE: requires Core Tools v4.0.6000+ (ships .NET 8) for Durable extension bundle v4.
#       Update: npm install -g azure-functions-core-tools@4 --unsafe-perm true
functions:
	source .funcvenv/Scripts/activate && PYTHONPATH="$$(pwd)" func start --port 7071

dev: azurite-up
	@echo "Start in 3 terminals: 'make mcp' / 'make server' / 'make functions'"

test:
	uv run pytest -v

clean:
	docker compose down -v
	rm -rf .venv .funcvenv .python_packages __pycache__ .pytest_cache .ruff_cache azurite-data
