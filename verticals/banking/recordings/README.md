# Banking curated recordings

Recorded walks for the Banking pack live here, one JSONL file per workflow
type, committed so the deployed replay surface can play them back without a
live runtime.

Record them with the blueprint recorder against a live stack:

```bash
curl -X POST http://localhost:3101/api/blueprint/_recorder/start
# drive the hero and let the ramp loop run
curl -X POST http://localhost:3101/api/blueprint/_recorder/stop
ls -la data/blueprint-recordings/app-fraud-reimbursement-*.jsonl
```

A recording is only valid if the walk it captured actually completed. Do not
commit a partial or single-event file.
