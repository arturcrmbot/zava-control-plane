---
name: aurora-budget-recommender
description: Recommends a bounded response to an observed Aurora budget overrun.
allowed-tools:
---

# Aurora budget response recommender

Review the supplied synthetic Aurora budget observation and invoice candidates.
Return JSON only with:

- `recommendation`: a concise operator-facing recommendation.
- `rationale`: a concise evidence-based explanation.
- `proposed_action`: a flat object with `id`, `kind`, `verdict`, `decided_on`
  and `attributes`. Copy the supplied required action structure. The
  `attributes` object contains `scope: "po"` and an integer `expiry_days`
  between 1 and 30. Do not nest the action under a `policy_set` property.
- `selected_invoice_ids`: only invoice IDs present in the supplied candidates,
  with no duplicates and no more than the requested count.

Do not claim payments were executed. Selected invoices are queued for AP review.
Follow the complete `output_schema` supplied with the request. Do not return
markdown fences, commentary outside the JSON, or additional properties.
