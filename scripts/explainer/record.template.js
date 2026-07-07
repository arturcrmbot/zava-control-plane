// record.template.js — playwright-cli run-code body.
//
// CONTRACT: This file is NOT runnable directly. record.sh substitutes the
// inline placeholder tokens (CFG, SUBSET, VIDEO_PATH) with the contents of
// scenes.json (as a JS literal) and writes the result to dist/record.runtime.js,
// which is then passed to `playwright-cli run-code --filename`.
//
// Why this dance: the sandbox in which playwright-cli evaluates --filename
// scripts has no `require()`, no `__dirname`, no fs access. The only way to
// give it data is to bake it into the file.
//
// The trailing arrow function MUST NOT have a trailing semicolon (cli wraps
// the source as `const fn = SRC; fn(page);` so `};` becomes `};;`).

async page => {
  const cfg = __INLINE_CFG__;
  const subsetIds = __INLINE_SUBSET__;
  const videoOutPath = __INLINE_VIDEO_PATH__;
  const scenes = subsetIds.length
    ? cfg.scenes.filter(s => subsetIds.includes(s.id))
    : cfg.scenes;

  // ----- dark mode injection ---------------------------------------------
  // Operator (web/client) uses a useDarkMode hook that:
  //   - Reads `fleetctl.theme` from localStorage (JSON-encoded "light"|"dark"|"system")
  //   - Falls back to prefers-color-scheme
  //   - Owns the <html class="dark"> toggle via useEffect, so just adding the
  //     class in init script gets stomped on mount.
  // We therefore (a) seed localStorage with "dark" so the hook resolves dark,
  // and (b) emulate prefers-color-scheme dark as a belt-and-braces fallback.
  // Blueprint / external sites ignore both.
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem('fleetctl.theme', '"dark"');
      document.documentElement.classList.add('dark');
    } catch {}
  });

  // ----- overlay helpers --------------------------------------------------

  let cardHighlight = null;
  let chyron = null;

  const showChyron = async (text) => {
    if (chyron) { await chyron.dispose(); chyron = null; }
    chyron = await page.screencast.showOverlay(`
      <div style="position: absolute; bottom: 28px; left: 28px;
        padding: 9px 16px; background: rgba(20,20,24,0.85);
        color: #f3c898;
        font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
        font-size: 14px; font-weight: 500; letter-spacing: 0.02em;
        border-radius: 8px; backdrop-filter: blur(10px);
        border: 1px solid rgba(208,143,72,0.35);
        box-shadow: 0 4px 18px rgba(0,0,0,0.25);">
        ${text}
      </div>`);
  };

  const clearChyron = async () => {
    if (chyron) { await chyron.dispose(); chyron = null; }
  };
  const argumentCardHandle = async (idx) => {
    const h = await page.evaluateHandle((i) => {
      const list = document.querySelectorAll('.argument__list')[0];
      if (!list) return null;
      return list.querySelectorAll('.argument__item')[i] || null;
    }, idx);
    return h.asElement();
  };

  const cardLabels = ['the harness', 'skills', 'mcps', 'the foundation'];

  const highlightCard = async (idx) => {
    if (cardHighlight) { await cardHighlight.dispose(); cardHighlight = null; }
    const handle = await argumentCardHandle(idx);
    if (!handle) { console.warn(`no card handle ${idx}`); return; }
    await handle.scrollIntoViewIfNeeded();
    await page.waitForTimeout(600);
    const box = await handle.boundingBox();
    if (!box) { console.warn(`no bbox ${idx}`); return; }
    cardHighlight = await page.screencast.showOverlay(`
      <div style="position: absolute;
        top: ${box.y - 6}px; left: ${box.x - 6}px;
        width: ${box.width + 12}px; height: ${box.height + 12}px;
        border: 2px solid rgba(208,143,72,0.85);
        border-radius: 14px;
        box-shadow: 0 0 0 6px rgba(208,143,72,0.18), 0 0 28px rgba(208,143,72,0.35);
        pointer-events: none;"></div>
      <div style="position: absolute;
        top: ${box.y + box.height + 10}px; left: ${box.x}px;
        padding: 4px 10px; background: rgba(208,143,72,0.92); color: #1a1611;
        font-family: -apple-system, 'Segoe UI', sans-serif;
        font-size: 12px; font-weight: 600; letter-spacing: 0.03em;
        border-radius: 6px;">${cardLabels[idx]}</div>`);
  };

  const clearCardHighlight = async () => {
    if (cardHighlight) { await cardHighlight.dispose(); cardHighlight = null; }
  };

  // ----- navigation / scroll helpers --------------------------------------

  const urlFor = (stage) => {
    switch (stage.page) {
      case 'essay':              return cfg.essay_url;
      case 'operator':           return cfg.operator_url;
      case 'operator_workflow':  return cfg.operator_workflow_url;
      case 'operator_memory':    return cfg.operator_memory_url;
      case 'operator_knowledge': return cfg.operator_knowledge_url;
      case 'constellation_view': return cfg.constellation_view_url;
      case 'constellation_site': return cfg.constellation_site_url;
      default: throw new Error(`unknown page: ${stage.page}`);
    }
  };

  const scrollToText = async (text, align = 'start') => {
    const found = await page.evaluate(({ text, align }) => {
      const nodes = document.querySelectorAll('h1,h2,h3,p,blockquote,li,div');
      const needle = text.toLowerCase();
      for (const n of nodes) {
        // Match text directly in the node, not in descendants, to keep scoping tight.
        const own = Array.from(n.childNodes)
          .filter(c => c.nodeType === 3)
          .map(c => c.textContent)
          .join(' ')
          .toLowerCase();
        if (own.includes(needle)) {
          n.scrollIntoView({ behavior: 'smooth', block: align });
          return true;
        }
      }
      // Fallback: any descendant text.
      for (const n of nodes) {
        if (n.textContent && n.textContent.toLowerCase().includes(needle)) {
          n.scrollIntoView({ behavior: 'smooth', block: align });
          return true;
        }
      }
      return false;
    }, { text, align });
    if (!found) console.warn(`scrollToText miss: "${text}"`);
    await page.waitForTimeout(900);
  };

  // Click an element by visible text (button/link/role=button). Case-insensitive.
  const clickText = async (text) => {
    const ok = await page.evaluate((needle) => {
      const want = needle.trim().toLowerCase();
      const candidates = Array.from(document.querySelectorAll(
        'button, a, [role="button"], [role="tab"]'
      ));
      const exact = candidates.find(el => (el.textContent || '').trim().toLowerCase() === want);
      const partial = candidates.find(el => (el.textContent || '').trim().toLowerCase().includes(want));
      const target = exact || partial;
      if (!target) return false;
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      target.click();
      return true;
    }, text);
    if (!ok) console.warn(`clickText miss: "${text}"`);
  };

  // Scroll a text node into view by walking the DOM and calling scrollIntoView,
  // which scrolls the nearest scrollable ancestor — works for drawer panels too.
  const scrollDrawerToText = async (text) => {
    const ok = await page.evaluate((needle) => {
      const want = needle.toLowerCase();
      const nodes = document.querySelectorAll('aside h1, aside h2, aside h3, aside h4, aside h5, aside p, aside section, aside div, h3, h4, section');
      for (const n of nodes) {
        if ((n.textContent || '').toLowerCase().includes(want)) {
          n.scrollIntoView({ behavior: 'smooth', block: 'start' });
          return true;
        }
      }
      return false;
    }, text);
    if (!ok) console.warn(`scrollDrawerToText miss: "${text}"`);
  };

  // Generic text-element highlight (like highlightCard but for any DOM node by text).
  let textHighlight = null;
  const showTextHighlight = async (text) => {
    if (textHighlight) { await textHighlight.dispose(); textHighlight = null; }
    const box = await page.evaluate((needle) => {
      const want = needle.toLowerCase();
      const candidates = Array.from(document.querySelectorAll('a, button, h2, h3, li'));
      const target = candidates.find(el => (el.textContent || '').toLowerCase().includes(want));
      if (!target) return null;
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      const r = target.getBoundingClientRect();
      return { x: r.left, y: r.top, w: r.width, h: r.height };
    }, text);
    if (!box) { console.warn(`showTextHighlight miss: "${text}"`); return; }
    await page.waitForTimeout(400);
    textHighlight = await page.screencast.showOverlay(`
      <div style="position: absolute;
        top: ${box.y - 8}px; left: ${box.x - 10}px;
        width: ${box.w + 20}px; height: ${box.h + 16}px;
        border: 2px solid rgba(208,143,72,0.85);
        border-radius: 10px;
        box-shadow: 0 0 0 6px rgba(208,143,72,0.18), 0 0 28px rgba(208,143,72,0.4);
        pointer-events: none;"></div>`);
  };
  const clearTextHighlight = async () => {
    if (textHighlight) { await textHighlight.dispose(); textHighlight = null; }
  };

  // ----- warm-up ----------------------------------------------------------
  // Skip constellation view: it boots a WebGL/Three.js scene that's heavy
  // enough to wedge the browser context if we hit it twice in quick succession.
  // The scene's own after_navigate_wait_ms (5500ms) is enough on a cold load.
  // Also skip constellation_site (external) — no need to prefetch.

  await page.setViewportSize(cfg.viewport);
  const warmTargets = [
    ['essay', cfg.essay_url, 2500],
    ['operator', cfg.operator_url, 2500],
    ['workflow detail', cfg.operator_workflow_url, 3000],
    ['memory', cfg.operator_memory_url, 3000],
    ['knowledge', cfg.operator_knowledge_url, 3000],
  ];
  for (const [name, url, settleMs] of warmTargets) {
    console.log(`warming ${name}...`);
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForTimeout(settleMs);
    } catch (e) {
      console.warn(`warm-up failed for ${name}: ${e.message}`);
    }
  }

  // Park back on essay for scene 1 start.
  await page.goto(cfg.essay_url, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(500);
  console.log('warm-up complete');

  // ----- record -----------------------------------------------------------

  // Defensively stop any leftover screencast from a previous interrupted run.
  try { await page.screencast.stop(); } catch {}

  console.log(`starting screencast → ${videoOutPath}`);
  await page.screencast.start({
    path: videoOutPath,
    size: { width: cfg.viewport.width, height: cfg.viewport.height },
  });

  const total = scenes.length;
  let lastPage = 'essay';

  for (let i = 0; i < scenes.length; i++) {
    const scene = scenes[i];
    const sceneStart = Date.now();
    console.log(`\n[scene ${i + 1}/${total}] ${scene.id} ${scene.label} (${scene.audio_ms}ms)`);

    const targetPage = scene.stage.page;
    if (targetPage !== lastPage) {
      console.log(`  nav → ${targetPage}`);
      await page.goto(urlFor(scene.stage), { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForTimeout(scene.stage.after_navigate_wait_ms || 1500);
      lastPage = targetPage;
    } else if (scene.stage.after_navigate_wait_ms) {
      await page.waitForTimeout(scene.stage.after_navigate_wait_ms);
    }

    if (scene.stage.scroll_sequence) {
      for (const step of scene.stage.scroll_sequence) {
        await scrollToText(step.to_text, step.align || 'start');
        if (step.wait_ms) await page.waitForTimeout(step.wait_ms);
      }
    } else if (scene.stage.scroll_to_text) {
      await scrollToText(scene.stage.scroll_to_text, scene.stage.scroll_align || 'start');
    }

    if (typeof scene.stage.highlight_card_index === 'number') {
      await highlightCard(scene.stage.highlight_card_index);
    } else if (!scene.stage.card_highlight_sequence) {
      // Don't clear if the scene plans to animate its own highlights.
      await clearCardHighlight();
    }

    if (scene.stage.highlight_text) {
      // Defer until after the main scroll; show it after a short delay.
      // Cleared on next scene that doesn't request a text highlight.
    } else {
      await clearTextHighlight();
    }

    if (scene.stage.chyron) {
      await showChyron(scene.stage.chyron.text);
    } else if (!scene.stage.chyron_persist_from_previous) {
      await clearChyron();
    }

    // Build deferred action promises that fire during the hold.
    const deferredPromises = [];

    if (scene.stage.card_highlight_sequence) {
      for (const step of scene.stage.card_highlight_sequence) {
        deferredPromises.push((async () => {
          try {
            await page.waitForTimeout(step.after_ms);
            await highlightCard(step.index);
          } catch (e) { console.warn(`card_highlight_sequence error: ${e.message}`); }
        })());
      }
    }

    if (scene.stage.mid_actions) {
      for (const action of scene.stage.mid_actions) {
        deferredPromises.push((async () => {
          try {
            await page.waitForTimeout(action.after_ms);
            if (action.click_text) {
              console.log(`  mid → click "${action.click_text}"`);
              await clickText(action.click_text);
            }
            if (action.scroll_drawer_to_text) {
              console.log(`  mid → scroll drawer to "${action.scroll_drawer_to_text}"`);
              await scrollDrawerToText(action.scroll_drawer_to_text);
            }
            if (typeof action.scroll_page_by === 'number') {
              console.log(`  mid → scroll page by ${action.scroll_page_by}px`);
              await page.evaluate((dy) => window.scrollBy({ top: dy, behavior: 'smooth' }), action.scroll_page_by);
            }
            if (action.scroll_to_text) {
              await scrollToText(action.scroll_to_text, action.scroll_align || 'start');
            }
          } catch (e) { console.warn(`mid_action error: ${e.message}`); }
        })());
      }
    }

    if (scene.stage.highlight_text) {
      deferredPromises.push((async () => {
        try {
          await page.waitForTimeout(scene.stage.highlight_text_after_ms || 1500);
          await showTextHighlight(scene.stage.highlight_text);
        } catch (e) { console.warn(`highlight_text error: ${e.message}`); }
      })());
    }

    const elapsed = Date.now() - sceneStart;
    const remaining = Math.max(500, scene.audio_ms - elapsed);
    console.log(`  action ${elapsed}ms, hold ${remaining}ms`);
    await Promise.all([
      page.waitForTimeout(remaining),
      ...deferredPromises,
    ]);

    // Inter-scene silent gap — matches the 700ms breath inserted by mux.sh
    // between audio clips. Visually holds the current frame so audio and
    // video stay in sync after concat.
    if (i < scenes.length - 1) {
      await page.waitForTimeout(700);
    }
  }

  await page.waitForTimeout(800);
  if (cardHighlight) await cardHighlight.dispose();
  if (textHighlight) await textHighlight.dispose();
  if (chyron) await chyron.dispose();
  await page.screencast.stop();
  console.log(`\ndone → ${videoOutPath}`);
}
