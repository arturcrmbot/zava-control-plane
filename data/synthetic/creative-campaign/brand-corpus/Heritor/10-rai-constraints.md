---
brand: Heritor
doc_kind: rai_constraints
title: Heritor — RAI constraints
---

# Heritor — RAI constraints

## Hard rules

1. **No AI-rendered watchmakers or hands.** Heritor's hands are real,
   named, photographed in Geneva. Generated hands are an integrity
   violation.
2. **No celebrity-coded prompts** (no "in the manner of Daniel
   Craig wearing a watch"). Block at prompt-construction.
3. **No competitor watch styling.** AI-rendered watches must read
   Heritor-coded (ink/brass/parchment + macro context), never Patek/
   Vacheron/A. Lange-coded.
4. **No smart-watch interfaces.** Off-category.
5. **No simulated archive footage.** Real archive only.

## Soft rules (flag)

- Render that lands in white-on-blue (Patek-coded) → flag.
- Render with watch on a wrist in a lifestyle setting → flag.
- Render of a movement that's mechanically implausible → flag for
  master-watchmaker review.
- Edition copy that's vague ("limited" without a number) → flag.

## Prompt-engineering notes

Prepend prompts with:

> "Heritage watchmaker macro composition. Movement close-up or watch
> face on parchment / ink-toned surface. Old-style figures. Geneva
> atelier context. Brass / parchment / ink palette."

Append:

> "No people. No wrists in lifestyle context. No competitor brands.
> Macro photography, archival reference."
