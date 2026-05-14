# Zava — 30-minute, three-act demo runbook

Audience: holding-company COO / CFO / Chief People Officer plus one technical
sponsor. Total budget: 30 minutes plus 5 minutes Q&A. Three acts, ten minutes
each. Five named personae spotlighted, three cross-functional decisions, one
crisis injection.

| Act | Theme | Headline outcome |
|---|---|---|
| 1 | Cold-load + org X-ray + concurrency reveal | "It is alive, and it is parallel." |
| 2 | Leave it running, fast-forward 4 hours | "It learns and it self-tunes overnight." |
| 3 | Crisis injection + audit trail | "It survives a Monday-morning client loss and can defend every decision." |

> Pre-flight: `make demo-reset` (clears history), `make demo-warm` (boots
> orchestrator + 5 subsidiaries + simulator + UI), browser at
> `http://localhost:5173/?view=constellation`, second tab on the audit ledger,
> third tab on a terminal.

---

## Act 1 — Cold-load + org X-ray + concurrency reveal (10 min)

**Goal:** establish that what the audience is looking at is a real,
multi-subsidiary org, not a slide.

### 1.1 The cosmic lens (≈90s)
- Open `http://localhost:5173/?view=constellation`.
- Wait for the cold-load animation. Point at the cosmic lens (E2 visualisation).
- Script: *"Every dot is a real persona. Every arc is a real contract,
  brief, or invoice that just moved between them. Nothing here is canned —
  the simulator behind it is producing this in real time."*

### 1.2 The five subsidiaries (≈2 min)
Walk the holding-network panel (E6) left to right and name each subsidiary
(E3 dataset). Pause one beat on each:

1. **Helix Creative** — the flagship creative agency.
2. **Northbeam Media** — programmatic + media-buying.
3. **Loomwright PR** — earned media and crisis comms.
4. **Vantage Insights** — strategy, research, brand planning.
5. **Forge Production** — physical + digital production house.

Point at the inter-subsidiary edges. Script: *"Those edges are intercompany
recharges, shared talent, and co-pitched briefs. They are live."*

### 1.3 The five named narrative arcs (≈2 min)
Hover the persona ribbon (D5). Call out, by name:

- **Aisha Rahman** — Group CFO, Helix.
- **Marcus Kowalski** — Senior Producer, Forge (will go on holiday in Act 3).
- **Priya Venkatesan** — Head of Strategy, Vantage.
- **Daniel Osei** — Producer, Forge (covers Marcus).
- **Lena Hoffmann** — Group Head of Talent.

Script: *"Each of these has a calendar, an inbox, an OOO state, a chain of
delegations, and an opinion. They will each take a decision in the next 10
minutes."*

### 1.4 Agency KPIs panel — live ticking (≈90s)
Point at the AgencyKPIs panel (E4). Read the four headline metrics:

- Gross profit per brand
- Utilisation per craft
- Pitch-to-win cycle time
- Intercompany recharge backlog

Refresh once. Numbers must visibly move. Script: *"The numbers you are
watching are the live aggregate of those five subsidiaries. No batch job."*

### 1.5 Concurrency reveal — 8 hand-curated workflows (≈3 min)
In the terminal:

```bash
./scripts/demo/act1-burst.sh    # fires 8 curated workflows in parallel
```

Workflows fired (audience does not need to see the script):

1. AP-invoice cascade — Soylent, £42k.
2. Pitch decision — new D2C brand "Kindling".
3. OOO routing event — Marcus marks himself out.
4. Talent reallocation — Forge → Helix, 2 producers.
5. Intercompany recharge — Northbeam → Vantage.
6. Trend-fired cadence — TikTok velocity spike (I5).
7. Auto-block rule install — failed vendor KYC (I2).
8. Routing rebalance — pitch backlog shifted (I4).

Switch back to the constellation. **Property #1 to point at:** two or more
rocket-trail animations land on the same city in the same wall-clock second.

Script: *"That is not a recording — that is the parallel orchestrator
landing decisions concurrently. A holding company runs in parallel; so does
this."*

### Act 1 close
*"So: real org, five subsidiaries, named humans, live KPIs, and it does
things in parallel. Now we leave it alone for four hours."*

---

## Act 2 — Leave it running, fast-forward 4 hours via time-scrub (10 min)

**Goal:** prove the system tunes itself without a human in the loop.

### 2.1 Drag the time-scrub slider (≈60s)
- Locate the J4 time-scrub control (bottom of the constellation).
- Drag the handle to the **+ 4 hours** detent. Wait for the lens to redraw.

Script: *"We just told it 'pretend it is now 1pm'. Everything you are about
to see is the system having run, autonomously, for four simulated hours
since Act 1."*

### 2.2 What's-new panel (≈3 min)
Open the J6 what's-new panel. Walk the three sections:

- **Auto-block rules installed (I2)** — read two examples aloud, e.g.
  *"Vendor 'Lighthouse Print' auto-blocked after 2 failed KYC reruns."*
- **Routing rebalances (I4)** — *"Pitch backlog redistributed: Helix → Vantage
  to absorb a strategy-heavy brief from Kindling."*
- **Trend-fired cadences (I5)** — *"TikTok velocity for Soylent crossed
  threshold; weekly cadence promoted to daily for the next 14 days."*

Script: *"None of those required a human. Each is a written-down rule the
system installed because it watched its own behaviour."*

### 2.3 Sparklines (≈2 min)
Point back at the AgencyKPIs panel. The sparklines (powered by J1 history)
now show four hours of curve. Note one falling, one rising.

Script: *"Pitch-to-win cycle is trending down — that is the routing change
working. Intercompany recharge backlog is up — we will fix that in Act 3."*

### 2.4 Read the J5 story-pack aloud (≈3 min)
Open `/api/story-pack/morning` (J5). It returns markdown. Read it
verbatim — it is written for a human exec briefing.

Sample lines to land on:

- *"Overnight, 47 invoices auto-cascaded; 2 escalated to Aisha."*
- *"Kindling pitch advanced to round 2; Priya owns."*
- *"Marcus out until Thursday; Daniel covering 6 active productions."*

Script: *"This is the artefact a CEO would actually read at 8am. The system
wrote it. No human edited it."*

### Act 2 close
*"So: it not only runs, it tunes itself, and it can explain what it did in
plain English. Now let us break it."*

---

## Act 3 — Crisis injection + audit trail (10 min)

**Goal:** prove resilience and defensibility under a worst-Monday scenario.

### 3.1 Inject the crisis (≈60s)
In the terminal:

```bash
curl -X POST http://localhost:8000/api/simulator/crisis/client-loss \
  -H 'content-type: application/json' \
  -d '{"client":"Soylent Group","reason":"renegotiated"}'
```

Script: *"That is the H7 crisis injector. We just told the system that
Soylent — the largest client across three subsidiaries — has renegotiated
out of two retainers."*

### 3.2 The four-way storm (≈3 min)
Within seconds, the constellation should fan out four concurrent
workflows. Name each as it lights up:

1. **Contract review** — Loomwright legal + Helix account team.
2. **Talent redeployment** — Lena reallocates 9 FTE off Soylent.
3. **Intercompany recharge** — pending Soylent recharges frozen pending review.
4. **Board prep** — Aisha's board-pack draft regenerates.

Script: *"Four cross-functional decisions, four subsidiaries, one event.
A normal holding company would handle this with three days of meetings.
This took 90 seconds."*

### 3.3 OOO routing kicks in (≈2 min)
Point at the talent-redeployment workflow. Marcus is the named owner of
two Soylent productions. He is on holiday (set in Act 1).

The H3 OOO router should visibly route both decisions to **Daniel Osei**.
A toast in the corner reads *"Marcus Kowalski OOO until Thu; routed to
Daniel Osei (delegation chain: Marcus → Daniel)."*

Script: *"Marcus is on a beach. Daniel covers. The delegation chain is
explicit and auditable. Nobody had to chase him on Slack."*

### 3.4 Decision-replay / audit ledger (≈3 min)
Switch to the audit-ledger tab. Pick the talent-redeployment decision.
Click **Replay**. The I7 endpoint:

```bash
curl http://localhost:8000/api/decisions/replay/<decision_id>
# => { "would_decide_same": true, "rationale": "...", "inputs_hash": "..." }
```

Script: *"This is the I7 decision-replay endpoint. Given the same inputs,
the system would still decide the same way. Every input, every rule
version, every persona state at decision time is hashed and pinned. That
is what a regulator or a board sub-committee actually wants."*

### 3.5 Network-effect close (≈60s)
Switch back to the constellation. The holding-network panel (E6) now shows
four subsidiaries glowing — the impact of one client event has rippled
across the holding.

Script: *"One client. Four subsidiaries. One coordinated response. One
audit trail. That is what a control plane for a 21st-century holding
company looks like."*

---

## Cheat-sheet: who appeared, what was decided

| Persona | Subsidiary | Acted in |
|---|---|---|
| Aisha Rahman | Helix (Group CFO) | Act 1 KPIs, Act 3 board prep |
| Marcus Kowalski | Forge | Act 1 OOO event, Act 3 (covered) |
| Priya Venkatesan | Vantage | Act 1 pitch, Act 2 routing |
| Daniel Osei | Forge | Act 3 OOO cover |
| Lena Hoffmann | Group Talent | Act 3 talent redeploy |

Cross-functional decisions surfaced (≥3 required):
1. Talent redeployment across Forge + Helix.
2. Intercompany recharge freeze across Northbeam + Vantage.
3. Board-pack regeneration spanning all 5 subsidiaries.

Crisis injections (≥1 required): 1 — `client-loss / Soylent`.
