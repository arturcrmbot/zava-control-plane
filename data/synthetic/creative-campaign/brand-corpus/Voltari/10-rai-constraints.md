---
brand: Voltari
doc_kind: rai_constraints
title: Voltari — RAI constraints for AI-generated assets
---

# Voltari — RAI constraints

## Hard rules (block outright)

1. **No human faces or recognisable bodies** in or around the vehicle.
   Driver seat shots: empty steering wheel only.
2. **No public-figure prompts.** No "in the manner of Elon Musk" or any
   other auto-industry public figure.
3. **No competitor vehicle styling.** AI-rendered cars must read
   Voltari-coded (warm neutrals, three-quarter view, asphalt context),
   never Tesla / Lucid / Polestar / BMW-coded.
4. **No comparison rendering.** Don't generate Voltari beside any other
   vehicle.
5. **No simulated charge-time / range numbers.** All quantitative
   claims come from the spec sheet, not the model.

## Soft rules (flag for human)

- Render that lands in pure-white-on-white (Tesla-coded) → flag.
- Render with visible driver / passenger silhouette → flag.
- Render in beach / vacation / lifestyle context → flag.
- Render where the brand's wordmark appears in any colour other than
  graphite `#0A1628` → flag.

## Prompt-engineering notes

Prepend prompts with:

> "Hero composition for a precision EV from Munich. Three-quarter view,
> matte paint on asphalt or factory courtyard. No driver, no
> passengers. Warm-neutral palette. Quantitative caption beneath."

Append:

> "No people. No faces. No drivers. No comparison to other vehicles.
> Engineering photography, not lifestyle photography."
