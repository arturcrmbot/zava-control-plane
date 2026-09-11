.PHONY: install dev mcp mcp-authority server functions funcvenv test test-harness test-e2e prove clean azurite-up azurite-down reset up down up-with-authority-mock agt-doctor agt-verify snapshot-save snapshot-restore snapshot-list data-pack-save

HARNESS_TEST_ENV = env -u PORTAL_DATA_DIR -u ZAVA_DATA_DIR -u ZAVA_WORLD_SCALE \
	ZAVA_VERTICAL=agency ZAVA_WORLD= ZAVA_MODE=live \
	PYTHON_DOTENV_DISABLED=1 ANONYMIZED_TELEMETRY=False \
	MEMORY_BACKEND=fallback LLM_RUNTIME=fake ENTITY_GRAPH_BUFFER_POOL_MB=256 \
	ENTITY_GRAPH_MAX_DB_SIZE_MB=4096 \
	AGT_DEV_KEYS=1 AGT_ENFORCE=0 AUTHORITY_MCP_URL= \
	AZURE_STORAGE_CONNECTION_STRING= AZURE_STORAGE_AUDIT_ACCOUNT= \
	APPLICATIONINSIGHTS_CONNECTION_STRING=
HARNESS_PYTEST = $(HARNESS_TEST_ENV) uv run --no-sync python -m pytest \
	-q --disable-warnings -o usefixtures=harness_offline

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

# Run only the delegated authority MCP standalone for ad-hoc inspection.
mcp-authority:
	cd mocks/authority-mcp && PORT=4108 npx tsx server.ts

server:
	uv run uvicorn api.server.main:app --port 3101 --reload

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
#
# Phase 3 TASK-025a: the authority-mcp Node mock (port 4108) is no longer
# part of the default boot. Authority resolve / check are served in-process
# by the governance kernel. Use `make up-with-authority-mock` (or set
# BOOT_DEMO_WITH_AUTHORITY_MOCK=1) to bring it up alongside for parity
# testing or for the engagement-POC swap-in dry run.
#
# We `env -u` the demo-config vars before invoking boot-demo.sh so that
# whatever a previous `source scripts/profile-everything.sh` left exported
# in this shell does not silently override the .env defaults. Without this
# guard, running constellation-mode in a shell and then re-running `make up`
# would auto-close every persona at boot and break the manual POC1+POC2
# walkthrough.
up:
	env -u PERSONA_AUTO_CLOSE \
	    -u SIMULATOR_RAMP_ENABLED \
	    -u SIMULATOR_RAMP_AVG_INTERVAL_SECONDS \
	    -u SIMULATOR_RAMP_DOMAINS \
	    -u PORTAL_SEED_REQS \
	    bash scripts/boot-demo.sh

# Bring up the full stack PLUS the authority-mcp Node mock on :4108.
# Pair with AUTHORITY_MCP_URL=http://127.0.0.1:4108 in env to actually
# route through the HTTP path (kernel is the default otherwise).
up-with-authority-mock:
	env -u PERSONA_AUTO_CLOSE \
	    -u SIMULATOR_RAMP_ENABLED \
	    -u SIMULATOR_RAMP_AVG_INTERVAL_SECONDS \
	    -u SIMULATOR_RAMP_DOMAINS \
	    -u PORTAL_SEED_REQS \
	    BOOT_DEMO_WITH_AUTHORITY_MOCK=1 bash scripts/boot-demo.sh

# Stop everything `make up` started, including grandchildren that
# `boot-demo.sh`'s SIGINT trap can leak (notably `func` itself, which
# starts in its own process group). Idempotent — safe to run when
# nothing is up. Uses pkill -f matching on stable substrings of each
# process command line.
down:
	@bash scripts/down-demo.sh

test:
	uv run pytest -q
	npm test --silent

# Replay collection configures a different AppState: keep it in its own process.
test-harness:
	$(HARNESS_PYTEST) \
		tests/api/shared/test_vertical_loader.py \
		tests/api/shared/test_vertical_pack_inventory.py \
		tests/api/shared/test_vertical_pack_validation.py \
		tests/api/shared/test_vertical_pack_contracts.py \
		tests/tools/test_runtime_image_contract.py \
		tests/tools/test_container_entrypoint.py \
		tests/tools/test_local_demo_configuration.py \
		tests/tools/test_public_replay_manifest.py \
		tests/tools/test_public_story_deployment.py \
		tests/api/server/test_static_production.py \
		tests/api/server/services/test_entity_graph_buffer_pool.py \
		tests/api/server/services/test_entity_graph_schema.py \
		tests/api/unit/test_webhook_delivery.py \
		tests/api/unit/test_tracked_executor_validation.py \
		tests/api/server/services/test_workflow_event_ingestor.py \
		tests/api/server/services/test_persona_responder_edge_cases.py \
		tests/api/server/services/test_platform_actor.py \
		tests/api/server/services/test_aurora_operator_guard.py \
		tests/api/server/services/test_aurora_workflow_ingestion.py \
		tests/api/server/routes/test_aurora_demo_trigger.py \
		tests/api/server/routes/test_aurora_operator_decision.py \
		tests/api/server/routes/test_internal_agency_aurora.py \
		tests/api/server/routes/test_blueprint_stream.py \
		tests/api/server/routes/test_blueprint_stream_backpressure.py \
		tests/api/server/routes/test_health_and_authority_health.py \
		tests/api/server/test_aurora_budget_response_domain.py \
		tests/api/server/test_ap_invoice_domain.py \
		tests/api/functions/test_kernel_registration.py \
		tests/api/functions/test_vertical_skill_root.py \
		tests/api/functions/workflows/test_aurora_budget_response.py \
		tests/api/functions/workflows/test_aurora_budget_response_activities.py \
		tests/api/functions/workflows/test_fleet_ap_invoice_decisions.py \
		tests/api/unit/test_hiring_segment_*.py \
		tests/api/unit/test_expense_claim_orchestration.py \
		tests/api/unit/test_*graph.py \
		tests/api/functions/agents/test_runtime_protocol.py \
		tests/api/functions/graphs/executors/agents/test_runtime_aoai.py \
		tests/api/functions/graphs/executors/agents/test_wrapper_tool_capture.py \
		tests/api/unit/test_fleet_manager_queue*.py \
		tests/api/unit/test_fleet_manager_service.py
	$(HARNESS_PYTEST) \
		tests/api/server/services/replay/test_reflector_isolation.py \
		tests/api/server/services/replay/test_recorder.py \
		tests/api/server/services/replay/test_player.py \
		tests/api/server/services/replay/test_hydrate.py \
		tests/api/server/services/replay/test_tape_format.py \
		tests/api/server/routes/test_replay_meta.py
	npm exec --no -- vitest run \
		web/client/hooks/__tests__/useResolutionStore.test.tsx \
		web/client/hooks/__tests__/useFeedItems.test.tsx \
		web/client/components/feed/__tests__/cards \
		web/client/components/feed/__tests__/Feed.test.tsx \
		web/client/components/feed/__tests__/CardList.test.tsx \
		web/client/components/feed/__tests__/Drawer.test.tsx \
		web/client/components/feed/__tests__/DrawerDecision.test.tsx \
		web/portal/src/lib/__tests__/paths.test.ts \
		web/blueprint/src/lib/__tests__/useReplayMode.test.ts \
		web/blueprint/src/components/cosmicLens/HUD/__tests__/guidedJourney.test.ts \
		web/blueprint/src/components/cosmicLens/HUD/__tests__/Narrator.test.tsx \
		web/blueprint/src/components/cosmicLens/HUD/__tests__/StoryGuide.test.tsx \
		web/blueprint/src/components/cosmicLens/HUD/__tests__/DemoHUD.test.tsx \
		web/blueprint/src/components/cosmicLens/HUD/__tests__/VitalSignsBar.test.tsx \
		web/blueprint/src/components/cosmicLens/HUD/__tests__/usePanelVisibility.test.ts \
		web/blueprint/src/pages/__tests__/ConstellationPage.test.tsx \
		web/blueprint/src/sections/__tests__/StoryContract.test.ts

# Playwright — requires the stack to already be running (`make up` in another terminal).
test-e2e:
	npx playwright test --reporter=list

prove:
	@test -n "$(VERTICAL)" || (echo "VERTICAL is required" >&2; exit 2)
	@test -x "tools/$(VERTICAL)_zava_e2e_proof.sh" || (echo "no proof runner for $(VERTICAL)" >&2; exit 2)
	ZAVA_VERTICAL="$(VERTICAL)" "tools/$(VERTICAL)_zava_e2e_proof.sh"

clean:
	docker compose down -v
	rm -rf .venv .funcvenv .python_packages node_modules dist __pycache__ .pytest_cache .ruff_cache azurite-data test-results

# --- Governance (AGT) -------------------------------------------------------
# See plan/archive/feature-agent-governance-toolkit-1.md (TASK-006). The two
# targets below are the operator-facing entry points to the Microsoft
# Agent Governance Toolkit CLI; they run against whatever's installed
# in the project venv (`uv sync`).

agt-doctor:
	.venv/bin/agt doctor

agt-verify:
	.venv/bin/agt verify

snapshot-save:        ## save the current sim state to data/snapshots/<NAME>.tgz (NAME=<your-name>)
	uv run python scripts/zava-snapshot.py save "$(NAME)"

snapshot-restore:     ## restore data/snapshots/<NAME>.tgz over the live db
	uv run python scripts/zava-snapshot.py restore "$(NAME)"

snapshot-list:        ## list available snapshots
	uv run python scripts/zava-snapshot.py list

data-pack-save:       ## materialise the Zava DataPack into data/portal/entity_graph.kuzu and snapshot it
	uv run python -c "from api.server.data_fabric.pack import build_zava_pack; r = build_zava_pack().materialise('data/portal/entity_graph.kuzu'); print(r)"
	uv run python scripts/zava-snapshot.py save zava-baseline
