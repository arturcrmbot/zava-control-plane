# Document Intelligence skill — design

**Date:** 2026-04-30
**Scope:** POC1 receipts + POC2 CVs — wire real Azure AI Document Intelligence as an OCR layer behind the existing receipt-validator and cv-crystalliser skills, via a single new skill + a single new MCP tool.
**Out of scope:** Blob storage migration; rewiring the other 9 hiring phase stubs; voice (ACS + GPT-Realtime).

## Decisions captured during brainstorm

| # | Question | Decision |
|---|---|---|
| 1 | Subsystems in scope | POC1 receipts + POC2 CV intake. Other 9 hiring phases and voice stay out. |
| 2 | Where do real services run | Real Azure cloud — user provisions Document Intelligence resource. |
| 3 | Receipt OCR architecture | Document Intelligence + GPT-4.1 vision in series. DI extracts structured fields with confidence; vision skill cites them in evidence. |
| 4 | CV PDFs | All 50 hand-crafted by Claude via `weasyprint`. Multiple templates + salted edge cases. |
| 5 | CV OCR architecture | Same as receipts — DI layout/general-document model + vision skill in series. |
| 6 | Files local or in Blob | Local only. Files stay in `data/synthetic/`. No Blob in this design. |
| 7 | MCP tool vs skill-only | MCP tool kept — code-execution capability would bypass audit-ledger, hooks, and `allowed-tools` discipline that the WPP narrative depends on. |

## §1 — Architecture

Two orchestrator phases get a new pre-OCR step. No new agent executors.

**POC1 Phase 3 (Validate Receipt):** existing `agent_receipt_validator.py` flow unchanged. The receipt-validator skill gains a Step 0: call `ocr_extract` with the `prebuilt-receipt` model. Then run the existing image-comparison logic, citing DI fields + confidences in evidence.

**POC2 Phase 4 (Triage):** the cv-crystalliser skill gains a Step 0: call `ocr_extract` with the `prebuilt-layout` model. The skill then maps DI's text blocks, tables, and key-value pairs to the canonical profile schema. *Wiring `cv-crystalliser` into [api/functions/graphs/triage.py](api/functions/graphs/triage.py) (replacing `agent_hiring_stub`) is explicitly OUT OF SCOPE for this design — the skill becomes ready-to-use; one-line wiring change ships separately when POC2 is taken off stub.*

**New components (all small):**
- `api/server/skills/use-document-intelligence/SKILL.md` — runbook (no code)
- `api/server/mcp_tools/ocr_extract.py` — ~40-line MCP tool wrapping `azure-ai-documentintelligence`
- `data/synthetic/hiring/cvs/generate_pdfs.py` — generator script
- `data/synthetic/hiring/cvs/pdfs/{candidate_id}.pdf` × 50 — generated PDFs

**Modified components:**
- `api/server/skills/receipt-validator/SKILL.md` — Step 0 + frontmatter `allowed-tools: + ocr_extract` + `field_confidences` in output schema
- `api/server/skills/cv-crystalliser/SKILL.md` — Step 0 + frontmatter `allowed-tools: + ocr_extract` + per-field confidences in output schema
- `api/functions/graphs/executors/agents/agent_receipt_validator.py` — register the new tool on the session

## §2 — `ocr_extract` MCP tool spec

```python
@define_tool(name="ocr_extract", description="...")
def ocr_extract(params: _OcrExtractParams) -> ToolResult
```

**Pydantic params:**
- `document_id: str` — claim id (`CLM-*`) or candidate id (`C-*`). Tool resolves to local path internally.
- `model: Literal["prebuilt-receipt", "prebuilt-layout", "prebuilt-invoice", "prebuilt-document", "prebuilt-idDocument"]`

**Behaviour:**
1. Resolve `document_id` → local path. `CLM-*` → `data/synthetic/receipts/{id}.png`. `C-*` → `data/synthetic/hiring/cvs/pdfs/{id}.pdf`. Other prefixes → failure result.
2. Read bytes; SHA256.
3. Check in-memory cache keyed on `(sha256, model)`. Hit → return cached payload tagged `cached: true`.
4. Miss → call `DocumentIntelligenceClient(endpoint, key).begin_analyze_document(model, bytes)`. Wait for poller (~2-5s).
5. Trim DI's response: keep `documents[].fields` (with confidences), `tables[]`, `keyValuePairs[]`, `pages[].lines`. Drop bounding-box pixel coords.
6. Cache trimmed result; return.

**Wrap with `@traced_tool("ocr.extract")`** — span attributes `wpp.document.id`, `wpp.ocr.model`, `wpp.ocr.confidence_min`, `wpp.ocr.cache_hit`.

**Error paths:**
- File not found → `result_type="failure"`, agent recovers (existing missing-receipt path handles it).
- DI 4xx/5xx or timeout → `result_type="failure"`, skill prompt instructs vision-only fallback.
- Required env vars unset → fail-fast with named-var error message. No mock fallback.

**Registered with** `agent_receipt_validator` immediately. Reusable on any future agent that needs document OCR.

## §3 — `use-document-intelligence` skill content

Frontmatter:
```yaml
---
name: use-document-intelligence
description: How to OCR a document via Azure AI Document Intelligence — when to use which prebuilt model, how to call ocr_extract, how to interpret confidence scores, error handling.
allowed-tools: ocr_extract
---
```

Body sections:

1. **What + why** — one paragraph framing DI as the cloud OCR layer; call before reasoning over a document with vision.
2. **Model picker table** — five rows for the five whitelisted prebuilt models with "use this when…" decision tree.
3. **Canonical call shape** — single example showing `ocr_extract(document_id=..., model=...)` and trimmed response keys.
4. **Reading the response** — confidence interpretation thresholds (>0.9 trustworthy, 0.7-0.9 cite as uncertain, <0.7 escalate or fall back).
5. **Worked example A — receipt validation** — concrete prompt-shaped example for the receipt-validator skill.
6. **Worked example B — CV crystallisation** — concrete prompt-shaped example for the cv-crystalliser skill.
7. **When NOT to use** — caching is free for repeat doc calls but loops on the tool waste tokens; call once at start, store fields in working memory.
8. **Error handling** — what each failure type means; vision-only fallback prompt patterns.
9. **Cost note** — real Azure call billed per page; don't loop.

## §4 — Edits to existing skills

**`receipt-validator/SKILL.md`:**
- Frontmatter: `allowed-tools: claim_get_structured, ocr_extract` (add `ocr_extract`).
- New "Step 0" before existing Procedure: "Call `ocr_extract(document_id=claim_id, model='prebuilt-receipt')`. The structured fields it returns are your authoritative read of the receipt — primary evidence, with the attached image as a sanity check."
- Output JSON schema: add `field_confidences: {merchantName: float, total: float, transactionDate: float}` block.
- Evidence-sentence pattern updated: `"Document Intelligence reads merchantName='NOT-Côte Brasserie' (conf 0.94); claim asserts vendor='Côte Brasserie'."`
- Missing-receipt short-circuit unchanged — still bypasses the OCR step.

**`cv-crystalliser/SKILL.md`:**
- Frontmatter: `allowed-tools: linkedin_profile_fetch, ocr_extract` (add `ocr_extract`).
- New "Step 0" before existing Procedure: "Call `ocr_extract(document_id=candidate_id, model='prebuilt-layout')` to get text blocks, tables, and key-value pairs."
- Reading guidance: "Work history is usually in `tables[]` or sequential `pages[].lines`. Education same. Skills lists are often a 'Skills' section as KV pairs or comma-separated text."
- Output schema gains `inconsistencies[].confidence` and per-field confidence on `current_title`, `tenure_years_total`.

Both edits add only — no deletions to existing skill content.

## §5 — CV PDF generation

**Tool:** `weasyprint` (HTML+CSS → PDF). Added via `uv add weasyprint`.

**Generator:** `data/synthetic/hiring/cvs/generate_pdfs.py`. Reads each existing `C-*.json`. Picks template + salt deterministically by hash of candidate_id. Renders to `pdfs/{candidate_id}.pdf`.

**Templates (4, hand-authored HTML/CSS):**
- `classic-serif.html` — single-column, Garamond, traditional consulting/finance.
- `modern-sans.html` — single-column, Inter, generous whitespace, ad-tech vibe.
- `two-column.html` — left rail (skills/education/contact) + right column (work history/summary). Design-y.
- `technical.html` — work history as tables; skills tagged grid. Senior data engineer flavour.

**Template assignment by `current_title`:** senior data engineer → technical; creative director → two-column; media strategist → modern-sans; frontend engineer → two-column; werkstudent frontend → modern-sans. DE candidates on classic-serif get a "Werdegang" header.

**Salted edge cases (5 of 50):**
- 1 with embedded photo (base64 silhouette).
- 1 scanned-style (rendered then re-rasterised at 150 DPI with ~1.5° rotation).
- 1 multi-page (3 pages dense work history).
- 1 heavy-tables (work history + certifications + projects all as tables).
- 1 with appended passport-scan page (sets up §4.10 jurisdiction story).

**Idempotence:** deterministic seed; re-running produces byte-identical PDFs. Git diff stays clean.

**Output:** `data/synthetic/hiring/cvs/pdfs/`, 50 PDFs committed (~2-5MB total).

## §6 — Configuration

New env vars in both `.env` (FastAPI) and `local.settings.json` Values (func host):
```
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<resource>.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=<key>
```

`ocr_extract` reads at module load. Unset → fail-fast with named-var message.

New dependencies via `uv add`:
- `azure-ai-documentintelligence` (v1.0+ SDK)
- `weasyprint` (PDF generator only — could go under dev-deps)

Lockfile committed; `requirements.txt` re-exported via `uv export --no-dev --no-hashes --format requirements-txt -o requirements.txt`. Re-pip-install into `.funcvenv` after merging.

User provisions Document Intelligence resource in either `eastus` or `westeurope`. Key auth for demo; swap to Managed Identity for prod.

## §7 — Cost

- DI prebuilt-receipt: $0.15 / 1000 transactions. ~50 receipts × 100 demo runs ≈ $0.75.
- DI prebuilt-layout: $1.50 / 1000 pages. ~50 CVs × 1.2 avg pages × 100 runs ≈ $9.
- Cache cuts ~80% of repeat-run cost.
- Build-month ceiling: under $20.

## §8 — Out of scope (deferred)

- Wiring `cv-crystalliser` into [triage.py](../../../api/functions/graphs/triage.py) (replacing `agent_hiring_stub`). The skill is ready-to-use after this design ships; the wiring is a separate one-line change made when POC2 hiring goes off stub.
- Blob Storage migration. Files stay local in this design.
- Other 9 hiring phase stubs.
- Voice (ACS + GPT-Realtime).
- Managed Identity auth (key auth only for now).

## §9 — Risks / open questions

- **DI latency on demo cold start.** First call to a fresh resource can take 5-10s while the model warms. Mitigation: pre-warm on FastAPI lifespan startup with a 1-byte dummy call; or accept on first-spawn slowness.
- **DI quota.** Free tier is 500 pages/month. Standard tier is unmetered but billed. Confirm tier choice when provisioning.
- **PDF generation transitive deps.** `weasyprint` pulls GTK and Cairo on Windows — non-trivial system deps. Validate it installs cleanly into `.funcvenv` on the demo machine before relying on it.
- **Skill priming.** The agent only reads `use-document-intelligence` if the calling skill (`receipt-validator` / `cv-crystalliser`) references it. Verify the SKILL.md cross-reference syntax in the codebase's conventions.
