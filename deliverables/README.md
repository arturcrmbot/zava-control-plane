# WPP RFP — Submission Deliverables

All files in this folder are editable. Filenames are prefixed with their WPP §8 deliverable number so they line up with the brief's expected submission list.

**Deadline:** 2026-04-23.

## File inventory

| WPP §8 ref | File | Editable source | Notes |
|---|---|---|---|
| §8.1 | `01-questionnaire-response.xlsx` | — (Excel native) | 156 rows joined from the 29 domain answer CSVs onto WPP's original questionnaire template. Sheet layout preserved (Instructions + Questionnaire); WPP's original 5 columns followed by our 5 (Status, Response, Key Technologies, POC Demo, Reference). WPP's template has a duplicate "8.1" Ref label (typo for 8.10); matched by question text. |
| §8.2 | `02-written-response.docx` | — (Word native) | Populated master response document. 1,015 paragraphs, 11 tables, ~2.2 MB. Audit trail of the populator run in `02-written-response.report.md`. |
| §8.3 | `03-enterprise-architecture-diagram.png` | `03-enterprise-architecture-diagram.mmd` | Framework integrated with M365, Power Platform, Okta, multi-cloud, business systems; two-plane split (humans/Control Plane vs agents/Data Plane) visible; APIM as sole public edge. |
| §8.4 | `04a-c4-context.png` | `04a-c4-context.mmd` | C4 Level 1 — system context. 10 human actors + 18 external systems around our system. |
| §8.4 | `04b-c4-container.png` | `04b-c4-container.mmd` | C4 Level 2 — container decomposition. 8 container groups with relationship labels; Private Endpoint and dual-path telemetry encoded. |
| §8.4 | `04c-c4-component-fleet-manager.png` | `04c-c4-component-fleet-manager.mmd` | C4 Level 3 — Fleet Manager Agent decomposed into 9 components (input adapters, core reasoning, skill amplification, output delivery). |
| §8.5 | (embedded in `02-written-response.docx` §10.1 + Appendix B.4) | — | POC 1 Solution Architecture & Design lives inside the written response; not a separate file. |
| §8.6 | (embedded in `02-written-response.docx` §10.2 + Appendix B.5) | — | POC 2 Solution Architecture & Design lives inside the written response; not a separate file. |
| §8.7a | `07a-poc1-prd.docx` | `07a-poc1-prd.md` | POC 1 Finance Procure-to-Pay PRD. 19 sections, 12 pages, ~4,800 words. |
| §8.7b | `07b-poc2-prd.docx` | `07b-poc2-prd.md` | POC 2 HR Talent Lifecycle PRD. 19 sections, 11 pages, ~4,100 words. |
| §8.8 | (embedded in `02-written-response.docx` §11) | — | NFR table. |
| §8.9 | **Not yet produced** | — | High-Level Delivery Plan — separate work item. |
| §8.10 | **Account team deliverable** | — | Commercial Proposal — owned by the account team. |
| §8.11 | **Account team deliverable** | — | Testimonials + 3 reference contacts — owned by the account team. |

## Diagrams — editing

The `.mmd` files next to each `.png` are the Mermaid source. To re-render after editing:

```
mmdc -i deliverables/03-enterprise-architecture-diagram.mmd \
     -o deliverables/03-enterprise-architecture-diagram.png \
     -b white -w 2400
```

(Requires `@mermaid-js/mermaid-cli` — `npm install -g @mermaid-js/mermaid-cli` if not already installed.)

## PRDs — editing

Edit the `.md` source; regenerate the `.docx` via pandoc:

```
pandoc deliverables/07a-poc1-prd.md -o deliverables/07a-poc1-prd.docx
pandoc deliverables/07b-poc2-prd.md -o deliverables/07b-poc2-prd.docx
```

Or edit the `.docx` directly in Word — but be aware the `.md` is the version-controlled source; round-tripping from docx back to md loses fidelity.

## Regenerating the questionnaire xlsx

If any answer CSV changes under `response/questionnaire answers/`:

```
python -m helpers.build_questionnaire_xlsx
```

Default output is `deliverables/01-questionnaire-response.xlsx`.

## Regenerating the written response

If any authored MD under `content/authored/` changes, or the master docx is updated:

```
python -m helpers.populate_docx
```

Output is a timestamped sibling of the master in the OneDrive folder. Copy the latest over `deliverables/02-written-response.docx` when ready to ship.

## Residual items before 2026-04-23 submission

- High-Level Delivery Plan (WPP §8.9) — not yet produced.
- Commercial Proposal (§8.10) — account team.
- Testimonials + 3 reference contacts (§8.11) — account team.
- Inventory pass over `MSFT_Response/` for other Account-Team-authored v-PDFs that may need to be ported into the written response (spec §10a item B-1).
