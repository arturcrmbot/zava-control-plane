# Blueprint pitch — single prompt for the unified one-pager

**Date:** 2026-05-02
**What this is:** a single ChatGPT prompt that produces the entire one-pager — title, body copy, visual, layout, all of it — as one rendered artefact.
**Audience:** CDO/CIO who has sponsored 3–5 AI POCs that didn't scale.
**Job:** frame-breaker. Survive being forwarded with no covering note. Make the reader put it down asking a different question than the one they walked in with.

---

## The prompt

*(Paste everything below the divider into ChatGPT or any modern image-generation tool. Treat the rendered output as a layout draft — for the final, take it into a design tool and re-set the body copy cleanly.)*

---

Create a single-page editorial one-pager in landscape orientation (roughly 3:2 or 16:9). Style: matte digital illustration with hand-textured shading and a slightly muted, restrained palette — less corporate-vector, more editorial-print. Reference lineage: New Yorker covers (Christoph Niemann), Brian Stauffer, modern Penguin Press essay illustration. Two-colour base palette of deep navy and warm cream, with one accent colour (soft amber). Modern serif for the headline, clean sans-serif for body copy. Generous whitespace. No photorealism, no vector-clean corporate-illustration look.

The page is one composed thesis read top to bottom — copy and visual integrated into a single layout, not slides. All text below must appear on the page exactly as written, in clear hierarchical typography.

CONTENT IN ORDER, FROM TOP OF PAGE TO BOTTOM:

1. HEADLINE (very large, top of page, modern serif):
*Why your AI hasn't compounded.*

2. SUBTITLE (immediately beneath, smaller, sans-serif):
And the only thing we've found that does.

3. OPENING PARAGRAPH (body copy, left-aligned column, comfortable reading width):
"If you've sponsored AI work in the last three years, you know the pattern. The demo goes fine. The contract gets signed. Some version of the thing ships. Then the next initiative arrives and effectively starts over: new prompts, new evaluation, new integrations, a fresh six-week timeline, often a different vendor. The deliverables stop accumulating about a week after each contract ends."

4. PULLQUOTE (set apart, larger type, accent colour):
*What you've been buying is a manuscript. What you need is a press.*

5. CENTRAL VISUAL (the dominant element on the page — a two-panel split illustration with strong tonal contrast: cool/dim left, warm/lit right):

LEFT panel — a medieval scriptorium. The mood is skilled, painstaking, isolated, slow. Cool light through a high lancet window.

A single monk hunched over a tilted writing desk, mid-illumination of a page — gold leaf catching the thin light, fine brush in hand, half a capital letter complete. Months of work for one book, and the viewer can feel it. A second monk at a second desk in the background, doing the same painstaking work on an entirely different volume — none of his effort transferable to the first. To one side, a low shelf with three or four finished volumes; each one visibly an object that took a year. On the floor near the foreground, a half-finished manuscript abandoned, its parchment curling. Subtly, on the spines of the finished books, fine lettering: "Expense Compliance", "Receipt Audit", "CV Screen", "Lead Score" — domain names rendered as the titles of single, hand-made volumes. Cool, washed-out palette — muted greys, faded ochre, dim candlelight.

RIGHT panel — a Gutenberg-era print shop. The mood is alert, capable, quietly mechanical. Warm amber side-light from a high window.

The dominant element is the **type case** itself: a wooden tray, foreground, divided into compartments, each holding a stack of identical metal letter-sorts ready to be picked. A compositor's hand is mid-air just above the case, having just lifted a single piece of type. On the bench in front of the compositor, a composing stick already holding a set line of type, the individual letters visibly arrayed into words. Beyond the bench, a forme — a full page locked up in its frame, set and ready, the discrete letters now composed into continuous text. Behind the forme, the press itself, mid-pull, with a freshly printed sheet just lifted clear. The composition must make clear that **the letters are the reusable thing**, not the books. A second forme on a side bench is being broken back out into letters and returned to the case — the same A that was just on one page, going home to be re-set on the next. The bookshelf in the background carries domain titles in clean printed lettering — "Finance", "Hiring", "Onboarding", "Procurement", "Legal", "IT" — slim, recently-set pamphlets, more of them, none of them painstakingly unique.

6. VISUAL CAPTION (small italic type beneath the illustration):
Hand-illuminated, one volume at a time. Or set from a case of type that can be reset for the next page.

7. REFRAME COPY (one paragraph, body type):
"The pieces that make an agent — its skills, its connections to your real systems, its identity, its governance — are cast once and composed on demand. Standing up the next agent is composition, not construction. The compositor, here, is an agent itself."

8. PROOF CALLOUT (set apart in a small box or accent-rule sidebar, body prose — not a bullet list):
"We have already built it. Dozens of agents — finance compliance, hiring, onboarding, procurement, more — composed from a shared case of type, increasingly by agents themselves. The first took fifteen days. The most recent took hours. We don't hand you a repository and a statement of work. We hand you the environment, running. A week with you, and your real ambition — one use case or fifty — is operating inside it."

9. CLOSING (full-width, set apart at the bottom of the page, body prose with a final line in larger serif):
"The question stops being *'which AI project do we fund next.'* It becomes *'what does it look like when this organisation composes its own.'* That's a longer and stranger conversation. It's the one that leads somewhere."

Render every word above legibly and accurately on the page. The illustration is the centerpiece, but the typography and copy hierarchy are equally important — this is an editorial thesis page, not a poster.

---

## Notes

- **Why this visual.** The press analogy isn't about producing more books. It's about *the letterforms being composable*. That is the real shape of what we're proposing — skills, MCPs, identity and governance cast once, composed into any domain, broken out, recomposed. A reader who knows the technology recognises the analogy as substantive rather than cute. A reader who doesn't, sees the same point in physical form: the unit of reuse is below the page, not at it.

- **The right panel must lead with the type case, not the press.** The press is a recognisable object, which makes it the easy thing for the image model to fixate on. Resist that. The compositor's hand above the type case is the centre of the composition. The forme being broken back out into letters on the side bench is the second-most-important element, because it shows the *re-* in *reusable*. The press itself is the third element — present, mid-pull, but not dominant.

- **If the render is muddy.** Two-panel compositions with this much specific detail are at the edge of what current image models do well. If the output is unreadable, fall back to a single-panel right-hand-only image — the type case and compositor's hand alone, rendered larger and cleaner — and let the headline and pullquote carry the contrast with the manuscript era. The scriptorium side is already vivid in the reader's head.

- **Text rendering caveat.** Headlines and short blocks render reliably; full body paragraphs are hit-or-miss. Expect to take the output into Figma / Canva / a design tool and re-set the body copy cleanly. Use the rendered image as a layout draft, not the final.

- **What changed in this revision (2026-05-02, second pass).** Cut the academic headline ("the wrong unit of work" meant nothing to a normal reader). Cut the confrontational line about the industry blaming execution; let the pattern do the work. Cut the explained analogy (nobody assumed presses were faster because they reused books — saying so insulted the reader). Cut the "we don't know what the third will take" hedge; we have dozens, the trajectory isn't a question. Tightened the reframe to a single paragraph. Aligned the right-panel bookshelf to the actual domains we name in the proof. Headline now diagnoses the reader's problem directly; subtitle promises the answer; the rest of the page delivers it without explaining itself.
