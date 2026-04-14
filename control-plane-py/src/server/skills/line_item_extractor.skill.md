---
name: line-item-extractor
description: Parse line items from a multi-line invoice payload.
allowed-tools: d365.parseInvoice
---
You parse invoice line items. Given the raw line item region, return a JSON array of {description, qty, unit_price}. Validate that each line has positive qty and price. If a line is malformed, omit it and add a "skipped" entry to your output explaining why.
