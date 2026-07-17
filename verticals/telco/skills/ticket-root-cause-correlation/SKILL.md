---
name: ticket-root-cause-correlation
description: Correlates service tickets with network and order events.
---

# Ticket Root Cause Correlation

Use only supplied service evidence. Group tickets by accountable root cause and
flag vulnerable customers for review. Return only:

```json
{"ticket_ids":["TKT-..."],"root_cause":"network_site_failure","resolution":"...","reasoning":"..."}
```
