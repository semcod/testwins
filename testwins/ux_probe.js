({action, selector, contract: spec, outcome}) => {
  window.__testwinsUX?.dispose();
  // No text, attribute values or geometry leave the page: only aggregate observations.
  const one = s => {
    const xs = document.querySelectorAll(s);
    if (xs.length > 1) throw new Error('UX selector is ambiguous');
    return xs[0] || null;
  };
  const visible = el => {
    if (!el || !el.getClientRects().length) return false;
    for (let x = el; x; x = x.parentElement) {
      const st = getComputedStyle(x);
      if (st.visibility === 'hidden' || st.display === 'none' || Number(st.opacity) === 0) return false;
    }
    return true;
  };
  const feedback = () => {
    if (!spec.feedback) return false;
    const f = spec.feedback, el = one(f.selector);
    if (!visible(el)) return false;
    const normalize = s => s.replace(/\s+/g, ' ').trim();
    if (f.kind === 'visible') return true;
    if (f.kind === 'attribute') return el.getAttribute(f.name) === f.value;
    const text = normalize(el.innerText || '');
    return f.kind === 'text' ? text === normalize(f.value) : text.includes(normalize(f.value));
  };
  const signature = () => {
    if (!spec.visual_change) return null;
    const el = one(spec.visual_change);
    if (!el) return null;
    const st = getComputedStyle(el), r = el.getBoundingClientRect();
    return JSON.stringify([visible(el), el.innerText, ...['color','backgroundColor','borderColor','opacity','transform','fontWeight','display','visibility'].map(k => st[k]),
                           Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]);
  };
  const announce = () => {
    for (let el = one(spec.feedback.selector); el; el = el.parentElement) {
      const live = el.getAttribute('aria-live');
      if (live) return live === 'polite' || live === 'assertive';
      if (['status', 'alert', 'log'].includes(el.getAttribute('role'))) return true;
    }
    return false;
  };
  // Validate all selectors now, including currently absent result elements.
  one(selector);
  for (const k of ['focus', 'motion', 'visual_change']) if (spec[k]) one(spec[k]);
  const initialText = outcome?.kind === 'changed' ? document.body.innerText : null;
  const outcomeMatches = () => {
    if (!outcome) return false;
    const f = outcome;
    if (f.kind === 'changed') return document.body.innerText !== initialText;
    const xs = document.querySelectorAll(f.selector);
    if (f.kind === 'count') return xs.length === f.value;
    if (f.kind === 'count_min') return xs.length >= f.value;
    const el = one(f.selector);
    if (f.kind === 'hidden') return !visible(el);
    if (!el) return false;
    if (f.kind === 'visible') return visible(el);
    if (f.kind === 'focused') return el === document.activeElement;
    if (f.kind === 'checked') return !!el.checked;
    if (f.kind === 'unchecked') return !el.checked;
    if (f.kind === 'enabled') return !el.matches(':disabled') && el.getAttribute('aria-disabled') !== 'true';
    if (f.kind === 'disabled') return el.matches(':disabled') || el.getAttribute('aria-disabled') === 'true';
    if (f.kind === 'value') return el.value === f.value;
    if (f.kind === 'attribute') return el.getAttribute(f.name) === f.value;
    const normalize = s => s.replace(/\s+/g, ' ').trim();
    const text = normalize(el.textContent || '');
    return f.kind === 'text' ? text === normalize(f.value) : text.includes(normalize(f.value));
  };
  const initialOutcome = outcomeMatches();
  let outcomeUnmatched = !initialOutcome;
  const initialFeedback = feedback(), initialVisual = signature();
  let began = null, timer = null, stopped = false, sampleError = false;
  let seenUnmatched = !initialFeedback;
  const result = {input_observed: false, response_ms: null, feedback_ms: null,
                  feedback_preexisting: initialFeedback, outcome_preexisting: initialOutcome, outcome_ms: null, announced: false, visual_changed: false,
                  focus_matches: false, motion_target_observed: false, motion_ms: 0, infinite_motion: false};
  const sample = () => {
    if (began === null || stopped) return;
    const elapsed = performance.now() - began;
    try {
      const matchesOutcome = outcomeMatches();
      if (!matchesOutcome) outcomeUnmatched = true;
      if (matchesOutcome && outcomeUnmatched && result.outcome_ms === null) result.outcome_ms = elapsed;
      const matches = feedback();
      if (!matches) seenUnmatched = true;
      if (matches && seenUnmatched && result.feedback_ms === null) {
        result.feedback_ms = elapsed; result.announced = announce();
      }
      if (spec.visual_change && signature() !== initialVisual) result.visual_changed = true;
      if (spec.motion) {
        const el = one(spec.motion);
        if (el) result.motion_target_observed = true;
        for (const animation of el?.getAnimations({subtree: true}) || []) {
          if (!['running', 'pending'].includes(animation.playState) && !animation.pending) continue;
          const timing = animation.effect.getComputedTiming();
          if (!Number.isFinite(timing.endTime)) result.infinite_motion = true;
          else result.motion_ms = Math.max(result.motion_ms, timing.endTime);
        }
      }
    } catch (_) { sampleError = true; }
  };
  const events = {click:['pointerdown','click'], check:['pointerdown','click','change'], hover:['pointerover','mouseover'],
                  fill:['input'], select:['input','change'], press:['keydown']}[action];
  const onInput = event => {
    const el = one(selector);
    if (began !== null || !el || !(event.target === el || el.contains(event.target))) return;
    began = performance.now(); result.input_observed = true;
  };
  for (const event of events) document.addEventListener(event, onInput, true);
  const observer = new MutationObserver(sample);
  observer.observe(document.documentElement, {subtree:true, childList:true, attributes:true, characterData:true});
  timer = setInterval(sample, 16);
  const dispose = () => {
    stopped = true; clearInterval(timer); observer.disconnect();
    for (const event of events) document.removeEventListener(event, onInput, true);
  };
  window.__testwinsUX = {dispose, complete: async () => {
    result.response_ms = began === null ? null : performance.now() - began;
    // Observe the full bounded window so a late or long-running animation is not missed.
    const windowMs = Math.max(spec.feedback ? spec.feedback_ms : 0, spec.motion ? spec.motion_ms + 50 : 0);
    if (began !== null && windowMs > performance.now() - began)
      await new Promise(resolve => setTimeout(resolve, windowMs - (performance.now() - began)));
    sample();
    if (spec.focus) result.focus_matches = one(spec.focus) === document.activeElement;
    dispose();
    if (sampleError) throw new Error('UX observation failed');
    return result;
  }};
}
