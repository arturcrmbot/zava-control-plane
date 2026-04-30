---
name: use-document-intelligence
description: How to OCR a document via Azure AI Document Intelligence — when to use which prebuilt model, how to call ocr_extract, how to interpret confidence scores, error handling.
allowed-tools: ocr_extract
---

You use Azure AI Document Intelligence (DI) for OCR + structured extraction of any document — receipts, CVs, invoices, IDs. DI runs in the cloud; one call returns structured fields with per-field confidence scores, plus tables, key-value pairs, and full text lines. Always call DI **before** reasoning over a document with vision: the structured output anchors your verdict and the confidence scores carry through to the audit trail.

## Models

| Model | Use for | Returns |
|---|---|---|
| `prebuilt-receipt` | Expense receipt PNGs/JPGs | `documents[].fields.merchantName`, `total`, `transactionDate`, `items[]` |
| `prebuilt-layout` | CVs, generic forms, anything with structure | `tables[]`, `keyValuePairs[]`, `pages[].lines` (reading order) |
| `prebuilt-invoice` | Vendor invoices | `vendorName`, `invoiceTotal`, `lineItems`, customer fields |
| `prebuilt-document` | Unknown structure / fallback | Generic key-value pairs and tables |
| `prebuilt-idDocument` | Passports, visas, driver licences | `firstName`, `lastName`, `dateOfBirth`, `documentNumber`, `expirationDate` |

**Decision tree:**
- Receipt-type document → `prebuilt-receipt`.
- CV / résumé / form-like document → `prebuilt-layout`.
- Vendor invoice → `prebuilt-invoice`.
- Right-to-work proof, passport, visa → `prebuilt-idDocument`.
- Anything else → `prebuilt-document`.

## How to call

```
ocr_extract(document_id="CLM-0042", model="prebuilt-receipt")
→
{
  "model": "prebuilt-receipt",
  "documents": [{"fields": {
      "merchantName": {"value": "Côte Brasserie", "confidence": 0.99},
      "total": {"value": 33.81, "confidence": 0.97},
      "transactionDate": {"value": "2026-04-01", "confidence": 0.95},
      "items": [...]
  }}],
  "tables": [...],
  "keyValuePairs": [...],
  "pages": [{"pageNumber": 1, "lines": ["Côte Brasserie", "Steak frites 22.00", ...]}],
  "cached": false
}
```

`document_id` is a domain identifier — `CLM-*` for expense claims, `C-*` for hiring candidates. The tool resolves to the local file. Don't pass paths.

## Reading the response

- `documents[].fields` is the structured extraction. Each field is `{value, confidence}`. Confidence is 0.0-1.0.
- `tables[]` is rendered tables (rowCount, columnCount, cells with row/column index).
- `keyValuePairs[]` is "Label: Value" extractions (e.g. "Email: alice@x.com").
- `pages[].lines` is the full text in reading order — use as a fallback when structured fields are missing.

**Confidence policy:**
- ≥0.9 → trustworthy, cite directly.
- 0.7-0.9 → cite but flag as uncertain in your evidence.
- <0.7 → escalate (treat as unknown, fall back to vision attachment, or return inconclusive).

## Worked example A — receipt validation

You're given `claim_id="CLM-0042"`. First call:

```
ocr_extract(document_id="CLM-0042", model="prebuilt-receipt")
```

From the response, extract `merchantName.value`, `total.value`, `transactionDate.value`, plus their confidences. Compare against the structured claim record (loaded via `claim_get_structured`). Cite the specific values and confidences in your evidence sentence:

> "Document Intelligence reads merchantName='NOT-Côte Brasserie' (conf 0.94); claim asserts vendor='Côte Brasserie'. Mismatch → flavour=wrong-vendor."

## Worked example B — CV crystallisation

You're given `candidate_id="C-SE-USA-00"`. First call:

```
ocr_extract(document_id="C-SE-USA-00", model="prebuilt-layout")
```

Map the response to the canonical profile schema:
- Work history → look in `tables[]` first (often rendered as a table); fall back to `pages[].lines` if rendered as prose.
- Education → same — usually a table or a "Education" section in `pages[].lines`.
- Skills → typically a comma-separated list under a "Skills" heading in `pages[].lines`, or a `keyValuePairs[]` entry with key `"Skills"`.
- Contact info → `keyValuePairs[]` with keys like `"Email"`, `"Phone"`, `"LinkedIn"`.

## When NOT to use

The tool caches by sha256 of the document bytes plus model id, so repeat calls with the same id+model return cached results for free. But don't loop on the tool — call once at the start of your skill, store the structured fields in your working memory, refer to them throughout.

## Error handling

A `failure` result_type with error `"AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is not configured"` → environment is broken; you cannot recover. Return your skill's best-effort verdict citing this in evidence.

A `failure` with error containing `"document not found"` → the upstream pipeline failed to put the file in place. For receipts, fall through to the existing `missing-receipt` flavour. For CVs, return your skill's "missing input" output with confidence 0.

A `failure` with another error (timeout, 5xx) → fall back to vision-only validation. The image is also attached to your session; describe what you can see directly and lower your confidence accordingly.

## Cost note

Each call is a real Azure billing event ($0.0015 per receipt, $0.0015 per CV page). Cache cuts repeats. Don't loop.
