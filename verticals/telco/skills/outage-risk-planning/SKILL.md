---
name: outage-risk-planning
description: Plans field resource pre-staging from weather and network risk evidence.
---

# Outage Risk Planning

Use only supplied evidence. Select the smallest pre-staging action that materially
reduces outage risk. Return only:

```json
{"technician_ids":["TECH-..."],"spare_part_kinds":["power"],"reasoning":"..."}
```
