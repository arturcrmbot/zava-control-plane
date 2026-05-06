---
brand: Solene
doc_kind: rai_constraints
title: Solene — RAI / safety constraints for AI-generated assets
---

# Solene — RAI constraints for AI-generated assets

These are the brand-specific constraints layered on top of platform RAI
(content_filter) for any AI-generated still or video. The
`brand-guardian` skill enforces them; violations cause the workflow to
emit a `content_safety_rejection` exception → FM picks it up.

## Hard rules (block outright)

1. **No human faces or recognisable bodies.** Hands at wrist crop only.
   AI-rendered faces are a brand-integrity violation as well as an RAI
   risk (Solene never uses humans in hero, even photographed ones).
2. **No public-figure prompts.** Even by allusion ("a Catherine
   Deneuve-coded silhouette") — block at prompt-construction time.
3. **No copyrighted characters or motifs.** Check against the brand
   library before render.
4. **No simulated harvest scenes.** Every botanical-in-environment shot
   must reference an actual harvest the atelier has documented.
5. **No religious symbolism.** Even subtle background shapes (manger
   silhouettes, crosses, halos) — see AW24 retrospective.
6. **No celebrity allusions.** "In the manner of [name]" prompts are
   blocked at the prompt-construction stage.

## Soft rules (flag for human review, don't auto-block)

- Concept that grades into Solene's competitor palette (glossy black
  Margiela / clear amber Aesop) → flag for CD review.
- Tagline that fails the rubric (>3 words, second-person, superlative)
  → flag for copy review.
- Provenance claim wording that would fail EU 2024/825 → flag for legal.

## Prompt-engineering notes for `concept-curator`

When constructing prompts for `gpt-image-2`, prepend with:

> "Hero composition for a sustainable luxury fragrance house. No human
> faces or bodies. Botanical close-up or product still. Matte surfaces.
> Natural light. Pewter and ivory palette."

And append with:

> "No people. No faces. No religious symbols. Editorial photography,
> not advertising photography."

This reduces (but does not eliminate) the chance of an RAI rejection
or a brand-violation render.
