---
name: site-failure-diagnosis
description: Diagnoses imminent network asset failures from telemetry.
---

# Site Failure Diagnosis

Use only supplied telemetry. Identify the likely failing component, urgency, and
whether repair or replacement is justified. Return only:

```json
{"kind":"repair","priority":2,"reasoning":"..."}
```
