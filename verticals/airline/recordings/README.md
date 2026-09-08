# Airline Vertical Curated Recordings

## Overview

This directory holds **curated recordings** for the Airline vertical pack. Curated recordings are production-ready narrative replays of live Zava execution proofs that demonstrate domain behavior, recovery patterns, and actor coordination.

## Generation

Curated recordings are **generated only by live proof execution**, not created manually or imported from synthetic sources. The workflow is:

1. **Live Proof** (`proof/airline/`) executes a real airline scenario under the full Zava runtime
2. **Proof validates** and produces an audit trail (tape)
3. **Curation decision** occurs post-validation: does this tape become a canonical recording?
4. **If approved**, the tape is sealed and moved into this directory with a deterministic name

## Required Naming Convention

Once a tape is curated and moved into this directory, it follows the naming pattern:

```
{recording_id}.jsonl
```

Where `recording_id` is:
- Unique across the vertical
- Derived from the proof scenario (e.g., `hero2-stage2-golden-scenario`, `hero3-governance-flow`)
- Descriptive of the workflow type and phase it demonstrates
- Stable (does not change between proof runs)

Each curated recording is a newline-delimited JSON file (`.jsonl`) where each line is an event object, preserving the exact actor messages, durable function calls, and state transitions from the live proof.

## Current recordings

As of 2026-08-11, all three Airline heroes have curated recordings from the
validated live portfolio proof:

- `integrated-hub-disruption-recovery-20260811T181355-AIRHUB-0001.jsonl`
- `aog-engineering-recovery-20260811T181424-AOGA-0001.jsonl`
- `preemptive-schedule-resilience-20260811T181448-AIRSCHED-0001.jsonl`

## Integration

The Airline pack manifest declares this directory as a `RecordingSources` curated_dir:

```python
recordings=RecordingSources(curated_dirs=(PACK_ROOT / "recordings",))
```

At runtime, the Zava replay engine will discover `.jsonl` files in this directory and make them available for:
- Replay-mode proof validation (read-only baked scenarios)
- Agent training on real patterns
- Documentation and narrative generation
