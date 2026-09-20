'use strict';
/* Single HTML escaper for the whole bundle. Matches Python's html.escape(quote=True)
   exactly — including the apostrophe, which the four previous separate copies all
   omitted, leaving attribute-context sinks unescapable. */
function pesc(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' }[c];
  });
}
'use strict';
/*__RULES__*/
// Tabs (detail page)
document.querySelectorAll('.tabs').forEach(function (tabs) {
  var panels = tabs.parentElement;
  var tabButtons = [].slice.call(tabs.querySelectorAll('.tab'));
  var tabPanels = [].slice.call(panels.querySelectorAll('.tabpanel'));
  function activate(btn, moveFocus) {
    var name = btn.getAttribute('data-tab');
    tabButtons.forEach(function (t) {
      var on = t === btn;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    tabPanels.forEach(function (p) {
      var on = p.getAttribute('data-panel') === name;
      p.classList.toggle('is-active', on);
      p.hidden = !on;
      // Reveal a panel's blocks when its tab opens — IntersectionObserver is unreliable
      // for elements that were inside a display:none panel, so trigger it explicitly here.
      if (on) {
        var revs = p.querySelectorAll('.reveal');
        for (var i = 0; i < revs.length; i++) {
          (function (el, idx) { setTimeout(function () { el.classList.add('in'); }, Math.min(idx, 6) * 70); })(revs[i], i);
        }
      }
    });
    if (moveFocus) btn.focus();
  }
  activate(tabButtons.find(function (btn) { return btn.classList.contains('is-active'); }) || tabButtons[0], false);
  tabs.addEventListener('click', function (e) {
    var btn = e.target.closest('.tab');
    if (!btn) return;
    activate(btn, false);
  });
  tabs.addEventListener('keydown', function (e) {
    var cur = tabButtons.indexOf(document.activeElement);
    if (cur < 0) return;
    var next = null;
    if (e.key === 'ArrowRight') next = (cur + 1) % tabButtons.length;
    else if (e.key === 'ArrowLeft') next = (cur - 1 + tabButtons.length) % tabButtons.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = tabButtons.length - 1;
    if (next !== null) { e.preventDefault(); activate(tabButtons[next], true); }
  });
});

// Copy buttons
document.querySelectorAll('.copy-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var el = document.getElementById(btn.getAttribute('data-copy-target'));
    if (!el) return;
    var text = el.innerText;
    var done = function () {
      var old = btn.textContent;
      var status = document.getElementById('copyStatus');
      btn.textContent = 'Copied ✓'; btn.classList.add('copied');
      if (status) status.textContent = old + ' copied.';
      setTimeout(function () { btn.textContent = old; btn.classList.remove('copied'); }, 1600);
    };
    if (navigator.clipboard) { navigator.clipboard.writeText(text).then(done, done); }
    else {
      var ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta);
      ta.select(); try { document.execCommand('copy'); } catch (e) {} ta.remove(); done();
    }
  });
});

// Library search + filters
var results = document.getElementById('results');
if (results) {
  var state = { q: '', family: '', verifier: '', model: '', starter: false, data: [] };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };

  function chip(t, c) { return '<span class="chip ' + (c || '') + '">' + esc(t) + '</span>'; }
  function facets(p) {
    var out = [chip(p.family_title, 'chip-family')];
    if (p.starter) out.push(chip('starter', 'chip-starter'));
    if (p.verifier_type === 'mechanical' || p.verifier_type === 'judge' || p.verifier_type === 'mixed')
      out.push(chip(p.verifier_type + ' verifier', 'chip-verifier chip-' + p.verifier_type));
    out.push(chip(p.model_hint + ' model', 'chip-model'));
    return out.join('');
  }
  function card(p) {
    var alt = p.alt ? '<span class="pcard-alt">' + esc(p.alt) + '</span>' : '';
    return '<a class="pcard" href="prompt/' + p.id + '.html">' +
      '<span class="pcard-fam">' + esc(p.family_title) + '</span>' +
      '<span class="pcard-title">' + esc(p.title) + '</span>' + alt +
      '<span class="pcard-when">' + esc((p.when || '').slice(0, 120)) + '…</span>' +
      '<span class="pcard-foot">' + facets(p) + '</span></a>';
  }
  function match(p) {
    if (state.family && p.family_key !== state.family) return false;
    if (state.verifier && p.verifier_type !== state.verifier) return false;
    if (state.model && p.model_hint !== state.model) return false;
    if (state.starter && !p.starter) return false;
    if (state.q) {
      var hay = (p.title + ' ' + (p.alt || '') + ' ' + (p.full_title || '') + ' ' +
                 p.when + ' ' + p.family_title + ' ' + p.prompt_text).toLowerCase();
      if (hay.indexOf(state.q) === -1) return false;
    }
    return true;
  }
  function render() {
    var list = state.data.filter(match);
    results.innerHTML = list.map(card).join('');
    document.getElementById('count').textContent =
      list.length + ' of ' + state.data.length + ' prompts';
    document.getElementById('empty').hidden = list.length !== 0;
  }
  var bind = function (id, key, ev) {
    var el = document.getElementById(id); if (!el) return;
    el.addEventListener(ev || 'input', function () {
      state[key] = el.type === 'checkbox' ? el.checked
        : (key === 'q' ? el.value.toLowerCase().trim() : el.value);
      render();
    });
  };
  fetch('data/prompts.json').then(function (r) { return r.json(); }).then(function (d) {
    state.data = d;
    bind('q', 'q'); bind('f-family', 'family', 'change');
    bind('f-verifier', 'verifier', 'change'); bind('f-model', 'model', 'change');
    bind('f-starter', 'starter', 'change');
    render();
  });
}

/* ============================ MOTION SYSTEM ============================ */
(function () {
  'use strict';
  var motionOK = document.documentElement.classList.contains('motion-ok');
  var hasIO = 'IntersectionObserver' in window;
  document.addEventListener('visibilitychange', function () {
    document.documentElement.classList.toggle('tab-hidden', document.hidden);
  });

  // reveal-on-scroll, once
  (function () {
    var els = [].slice.call(document.querySelectorAll('.reveal'));
    if (!els.length) return;
    if (!motionOK || !hasIO) { els.forEach(function (e) { e.classList.add('in'); }); return; }
    var io = new IntersectionObserver(function (ents) {
      ents.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target, par = el.parentElement;
        var sibs = par ? [].slice.call(par.children).filter(function (c) { return c.classList.contains('reveal'); }) : [el];
        el.style.transitionDelay = Math.min(sibs.indexOf(el), 6) * 60 + 'ms';
        el.classList.add('in'); io.unobserve(el);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    els.forEach(function (e) { io.observe(e); });
  })();

  // counters: 0 -> real value, once, on view
  (function () {
    var els = [].slice.call(document.querySelectorAll('[data-target]'));
    if (!els.length) return;
    function run(el) {
      var target = parseFloat(el.getAttribute('data-target'));
      var dec = el.getAttribute('data-dec') === '1';
      var fin = function () { el.textContent = dec ? target.toFixed(1) : String(target); };
      // Real value is already in the HTML. Only animate when motion is on AND the tab is
      // visible; otherwise leave the true value (never show a stuck fabricated zero).
      if (!motionOK || document.hidden) { fin(); return; }
      el.textContent = dec ? '0.0' : '0';
      var start = null, dur = 1100;
      function tick(ts) {
        if (document.hidden) { fin(); return; }
        if (start === null) start = ts;
        var p = Math.min(1, (ts - start) / dur), e = 1 - Math.pow(1 - p, 3), v = target * e;
        el.textContent = dec ? v.toFixed(1) : String(Math.round(v));
        if (p < 1) requestAnimationFrame(tick); else fin();
      }
      requestAnimationFrame(tick);
    }
    if (!hasIO) { els.forEach(run); return; }
    var io = new IntersectionObserver(function (ents) {
      ents.forEach(function (en) { if (en.isIntersecting) { run(en.target); io.unobserve(en.target); } });
    }, { threshold: 0.5 });
    els.forEach(function (e) { io.observe(e); });
  })();

  // hero sequence
  (function () {
    var anim = document.getElementById('heroAnim'); if (!anim) return;
    var typed = anim.querySelector('.hero-typed'), full = typed ? (typed.getAttribute('data-text') || '') : '';
    var replay = anim.querySelector('.hero-replay'), timers = [];
    function clear() { timers.forEach(clearTimeout); timers = []; }
    function stat() { if (typed) typed.textContent = full; anim.classList.add('s2', 's3'); if (replay) replay.hidden = false; }
    function play() {
      clear(); anim.classList.remove('s2', 's3'); if (replay) replay.hidden = true;
      var i = 0;
      function type() {
        if (document.hidden) { timers.push(setTimeout(type, 140)); return; }
        i++; if (typed) typed.innerHTML = escapeHtml(full.slice(0, i)) + '<span class="caret"></span>';
        if (i < full.length) { timers.push(setTimeout(type, 20)); return; }
        if (typed) typed.innerHTML = escapeHtml(full) + '<span class="caret"></span>';
        timers.push(setTimeout(function () { anim.classList.add('s2'); }, 250));
        timers.push(setTimeout(function () { anim.classList.add('s3'); if (replay) replay.hidden = false; }, 950));
      }
      type();
    }
    var escapeHtml = pesc;
    if (!motionOK) { stat(); return; }
    if (replay) replay.addEventListener('click', play);
    if (hasIO) {
      var io = new IntersectionObserver(function (ents) {
        ents.forEach(function (en) { if (en.isIntersecting) { play(); io.unobserve(en.target); } });
      }, { threshold: 0.3 });
      io.observe(anim);
    } else play();
  })();

  // loop visualizer
  (function () {
    var root = document.getElementById('loopviz'); if (!root || !window.LOOPVIZ) return;
    var presets = window.LOOPVIZ, keys = Object.keys(presets);
    var ringWrap = root.querySelector('.lv-ring-wrap'), panel = root.querySelector('.lv-panel');
    var presetBar = root.querySelector('.lv-presets'), exitBar = root.querySelector('.lv-exits');
    var cur = keys[0], step = 0, playing = false, timer = null, speed = 1;
    var SVGNS = 'http://www.w3.org/2000/svg';

    function buildRing(steps) {
      var n = steps.length, cx = 115, cy = 115, r = 82;
      var svg = document.createElementNS(SVGNS, 'svg');
      svg.setAttribute('viewBox', '0 0 230 230'); svg.setAttribute('class', 'lv-ring');
      svg.setAttribute('role', 'group'); svg.setAttribute('aria-label', 'Loop with ' + n + ' steps');
      var circ = document.createElementNS(SVGNS, 'circle');
      circ.setAttribute('cx', cx); circ.setAttribute('cy', cy); circ.setAttribute('r', r); circ.setAttribute('class', 'lv-ring-path');
      svg.appendChild(circ);
      steps.forEach(function (s, i) {
        var a = -Math.PI / 2 + i * 2 * Math.PI / n, x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
        var g = document.createElementNS(SVGNS, 'g'); g.setAttribute('class', 'lv-node'); g.setAttribute('data-i', i);
        g.setAttribute('tabindex', '0'); g.setAttribute('role', 'button');
        g.setAttribute('aria-label', 'Go to step ' + (i + 1) + ': ' + s.label);
        var c = document.createElementNS(SVGNS, 'circle'); c.setAttribute('cx', x); c.setAttribute('cy', y); c.setAttribute('r', 8);
        var t = document.createElementNS(SVGNS, 'text'); t.setAttribute('x', x); t.setAttribute('y', y - 13);
        t.setAttribute('text-anchor', 'middle'); t.textContent = s.label;
        g.appendChild(c); g.appendChild(t);
        g.addEventListener('click', function () { pause(); step = i; render(); });
        g.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pause(); step = i; render(); }
        });
        svg.appendChild(g);
      });
      ringWrap.innerHTML = ''; ringWrap.appendChild(svg);
    }
    function render() {
      var d = presets[cur], s = d.steps[step];
      [].slice.call(ringWrap.querySelectorAll('.lv-node')).forEach(function (g, i) {
        g.classList.toggle('active', i === step); g.classList.toggle('done', i < step);
        g.setAttribute('aria-current', i === step ? 'step' : 'false');
      });
      panel.querySelector('.lv-step-label').textContent = 'Step ' + (step + 1) + ' / ' + d.steps.length;
      panel.querySelector('.lv-step-title').textContent = s.label;
      panel.querySelector('.lv-step-desc').textContent = s.desc;
      var q = panel.querySelector('.lv-quote'); q.hidden = !s.quote; if (s.quote) q.textContent = s.quote;
    }
    function next() { var d = presets[cur]; step = (step + 1) % d.steps.length; render(); }
    function prev() { var d = presets[cur]; step = (step - 1 + d.steps.length) % d.steps.length; render(); }
    function tick() { if (!playing) return; if (!document.hidden) next(); timer = setTimeout(tick, 1600 / speed); }
    function playPause() {
      playing = !playing;
      var play = root.querySelector('.lv-play');
      play.textContent = playing ? '⏸ Pause' : '▶ Play';
      play.setAttribute('aria-pressed', playing ? 'true' : 'false');
      if (playing && motionOK) { clearTimeout(timer); tick(); } else clearTimeout(timer);
    }
    function pause() {
      playing = false;
      var play = root.querySelector('.lv-play');
      play.textContent = '▶ Play'; play.setAttribute('aria-pressed', 'false');
      clearTimeout(timer);
    }
    function loadPreset(k) {
      cur = k; step = 0; pause();
      [].slice.call(presetBar.children).forEach(function (b) {
        var on = b.getAttribute('data-k') === k;
        b.classList.toggle('active', on);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      buildRing(presets[k].steps);
      var ex = presets[k].exits || {};
      exitBar.innerHTML = Object.keys(ex).map(function (name) {
        var cls = 'x-' + name.toLowerCase().replace('_', '');
        return '<button class="lv-exit ' + cls + '" data-exit="' + name + '" aria-pressed="false">' + name + '</button>';
      }).join('');
      [].slice.call(exitBar.children).forEach(function (b) {
        b.addEventListener('click', function () {
          pause();
          [].slice.call(exitBar.children).forEach(function (x) { x.classList.remove('fired'); x.setAttribute('aria-pressed', 'false'); });
          b.classList.add('fired');
          b.setAttribute('aria-pressed', 'true');
          panel.querySelector('.lv-step-title').textContent = 'Exit: ' + b.getAttribute('data-exit');
          panel.querySelector('.lv-step-desc').textContent = ex[b.getAttribute('data-exit')];
          panel.querySelector('.lv-quote').hidden = true;
        });
      });
      render();
    }
    [].slice.call(presetBar.children).forEach(function (b) {
      b.addEventListener('click', function () { loadPreset(b.getAttribute('data-k')); });
    });
    root.querySelector('.lv-play').addEventListener('click', playPause);
    root.querySelector('.lv-next').addEventListener('click', function () { pause(); next(); });
    root.querySelector('.lv-prev').addEventListener('click', function () { pause(); prev(); });
    root.querySelector('.lv-restart').addEventListener('click', function () { pause(); step = 0; render(); });
    var spd = root.querySelector('.lv-speed');
    if (spd) spd.addEventListener('click', function () {
      speed = speed >= 2 ? 0.5 : speed + 0.5;
      spd.textContent = speed + '×';
      spd.setAttribute('aria-label', 'Playback speed: ' + speed + ' times');
      if (playing) { clearTimeout(timer); tick(); }
    });
    root.addEventListener('keydown', function (e) {
      if (e.target !== root) return;
      if (e.key === 'ArrowRight') { pause(); next(); } else if (e.key === 'ArrowLeft') { pause(); prev(); }
      else if (e.key === ' ') { e.preventDefault(); playPause(); }
    });
    loadPreset(cur);
    var fb = root.querySelector('.lv-fallback'); if (fb) fb.hidden = true;
  })();

  // automation run simulation
  (function () {
    var flow = document.querySelector('.flow[data-run]'); if (!flow) return;
    var steps = [].slice.call(flow.querySelectorAll('.flow-step'));
    var runBtn = document.getElementById('autoRun'), sel = document.getElementById('autoCond');
    var status = document.getElementById('autoStatus'); if (!runBtn) return;
    var timers = [];
    function typeOf(el) { var b = el.querySelector('.flow-badge'); return b ? b.textContent.trim() : ''; }
    function clearRun() {
      timers.forEach(clearTimeout); timers = [];
      steps.forEach(function (s) { s.classList.remove('active', 'done', 'skipped', 'failed'); });
      if (status) status.textContent = '';
    }
    function findType(t) { for (var i = 0; i < steps.length; i++) if (typeOf(steps[i]) === t) return i; return -1; }
    function run() {
      clearRun();
      var cond = sel ? sel.value : 'success';
      var stopAt = steps.length, note = 'Completed successfully.';
      var fallbackIdx = findType('Fallback'), decIdx = findType('Decision gate'), valIdx = findType('Validation'),
        humanIdx = findType('Human approval'), detIdx = -1;
      steps.forEach(function (s, i) { if (typeOf(s) === 'Deterministic' && detIdx < 0) detIdx = i; });
      var branchTo = -1;
      if (cond === 'low-confidence' && (decIdx >= 0 || valIdx >= 0)) { stopAt = (decIdx >= 0 ? decIdx : valIdx) + 1; branchTo = fallbackIdx; note = 'Low confidence → routed to human review (fallback).'; }
      else if (cond === 'invalid-output' && valIdx >= 0) { stopAt = valIdx + 1; branchTo = fallbackIdx; note = 'AI output failed validation → fallback / retry.'; }
      else if (cond === 'human-reject' && humanIdx >= 0) { stopAt = humanIdx + 1; note = 'Human rejected the draft — nothing was sent.'; }
      else if (cond === 'api-timeout' && detIdx >= 0) { note = 'Deterministic step timed out → retried with backoff, then continued.'; }
      var i = 0, delay = motionOK ? 480 : 0;
      function walk() {
        if (i >= stopAt) {
          if (branchTo >= 0) { steps[branchTo].classList.remove('skipped'); steps[branchTo].classList.add('active');
            for (var k = 0; k < steps.length; k++) if (k >= stopAt && k !== branchTo) steps[k].classList.add('skipped'); }
          if (status) status.textContent = note; return;
        }
        var s = steps[i];
        if (cond === 'api-timeout' && i === detIdx) {
          s.classList.add('failed');
          timers.push(setTimeout(function () { s.classList.remove('failed'); s.classList.add('done'); i++; timers.push(setTimeout(walk, delay)); }, delay * 1.4));
          if (status) status.textContent = 'Timeout at deterministic step — retrying…';
          return;
        }
        s.classList.add('active');
        timers.push(setTimeout(function () { s.classList.remove('active'); s.classList.add('done'); i++; walk(); }, delay));
      }
      if (!motionOK) { for (var j = 0; j < stopAt; j++) steps[j].classList.add('done'); if (branchTo >= 0) steps[branchTo].classList.add('active'); if (status) status.textContent = note; return; }
      walk();
    }
    runBtn.addEventListener('click', run);
  })();
})();

/* prompt evolution stepper */
(function () {
  'use strict';
  var page = document.querySelector('.evolution-page'); if (!page) return;
  var dots = [].slice.call(page.querySelectorAll('.ev-dot'));
  var stages = [].slice.call(page.querySelectorAll('.ev-stage'));
  if (!dots.length) return;
  function show(i) {
    stages.forEach(function (s) {
      var on = +s.getAttribute('data-i') === i;
      if (on) s.setAttribute('data-active', ''); else s.removeAttribute('data-active');
      s.hidden = !on;
    });
    dots.forEach(function (d) {
      var on = +d.getAttribute('data-i') === i;
      d.classList.toggle('active', on);
      d.setAttribute('aria-selected', on ? 'true' : 'false');
      d.tabIndex = on ? 0 : -1;
    });
  }
  dots.forEach(function (d) { d.addEventListener('click', function () { show(+d.getAttribute('data-i')); }); });
  show(0);
  var bar = page.querySelector('.ev-dots');
  if (bar) bar.addEventListener('keydown', function (e) {
    var cur = dots.findIndex(function (d) { return d.classList.contains('active'); });
    var next = null;
    if (e.key === 'ArrowRight') next = (cur + 1) % dots.length;
    else if (e.key === 'ArrowLeft') next = (cur - 1 + dots.length) % dots.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = dots.length - 1;
    if (next !== null) { e.preventDefault(); show(next); dots[next].focus(); }
  });
})();

/* ===================== CONSTELLATION GRAPH ===================== */
(function () {
  'use strict';
  var wrap = document.getElementById('graphWrap');
  if (!wrap || !window.GRAPH) return;
  var G = window.GRAPH, N = G.nodes, E = G.edges, F = G.families.length;
  var SVGNS = 'http://www.w3.org/2000/svg';
  var W = 1000, H = 720, cx = 500, cy = 360, R = 260;
  var within = {};
  N.forEach(function (n) {
    var a = -Math.PI / 2 + n.f * 2 * Math.PI / F;
    var fx = cx + R * Math.cos(a), fy = cy + R * Math.sin(a);
    var k = (within[n.f] = (within[n.f] || 0)); within[n.f]++;
    var rr = 10 * Math.sqrt(k + 1), aa = (k + 1) * 2.399963;
    n.x = fx + rr * Math.cos(aa); n.y = fy + rr * Math.sin(aa);
    n.hue = Math.round(n.f / F * 360);
  });
  var esc = pesc;
  var svg = document.createElementNS(SVGNS, 'svg');
  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); svg.setAttribute('class', 'graph-svg');
  var gE = document.createElementNS(SVGNS, 'g');
  var edgeEls = E.map(function (e) {
    var l = document.createElementNS(SVGNS, 'line');
    l.setAttribute('x1', N[e.s].x.toFixed(1)); l.setAttribute('y1', N[e.s].y.toFixed(1));
    l.setAttribute('x2', N[e.t].x.toFixed(1)); l.setAttribute('y2', N[e.t].y.toFixed(1));
    l.setAttribute('class', e.c ? 'g-edge g-edge-cur' : 'g-edge'); gE.appendChild(l); return l;
  });
  svg.appendChild(gE);
  var adj = N.map(function () { return []; });
  E.forEach(function (e) { adj[e.s].push(e.t); adj[e.t].push(e.s); });
  var gN = document.createElementNS(SVGNS, 'g');
  var nodeEls = N.map(function (n, i) {
    var c = document.createElementNS(SVGNS, 'circle');
    c.setAttribute('cx', n.x.toFixed(1)); c.setAttribute('cy', n.y.toFixed(1)); c.setAttribute('r', 5);
    c.setAttribute('fill', 'hsl(' + n.hue + ',58%,52%)'); c.setAttribute('class', 'g-node');
    c.setAttribute('tabindex', '0'); c.setAttribute('role', 'button');
    c.setAttribute('aria-label', n.t + ' — ' + (G.families[n.f] ? G.families[n.f].title : ''));
    gN.appendChild(c); return c;
  });
  svg.appendChild(gN); wrap.appendChild(svg);
  var panel = document.getElementById('graphPanel');
  var lastGraphNode = null;
  function hi(i) {
    var near = {}; near[i] = 1; adj[i].forEach(function (j) { near[j] = 1; });
    nodeEls.forEach(function (el, j) { el.classList.toggle('dim', !near[j]); el.classList.toggle('hot', j === i); });
    edgeEls.forEach(function (el, j) { var on = E[j].s === i || E[j].t === i; el.classList.toggle('hot', on); el.classList.toggle('dim', !on); });
  }
  function clr() { nodeEls.forEach(function (el) { el.classList.remove('dim', 'hot'); }); edgeEls.forEach(function (el) { el.classList.remove('dim', 'hot'); }); }
  function closePanel() {
    if (!panel) return;
    panel.hidden = true;
    if (lastGraphNode) lastGraphNode.focus();
  }
  function open(i, moveFocus) {
    var n = N[i]; panel.hidden = false;
    panel.innerHTML = '<button class="g-close" aria-label="Close">×</button>' +
      '<span class="g-fam" style="color:hsl(' + n.hue + ',58%,44%)">' + esc(G.families[n.f].title) + '</span>' +
      '<h3>' + esc(n.t) + '</h3>' +
      (n.p.length ? '<div class="g-pats">' + n.p.map(function (p) { return '<span class="chip">' + esc(p) + '</span>'; }).join('') + '</div>' : '') +
      '<a class="btn btn-primary g-open" href="prompt/' + n.id + '.html">Open prompt →</a>';
    panel.querySelector('.g-close').addEventListener('click', closePanel);
    if (moveFocus) panel.querySelector('.g-open').focus();
  }
  nodeEls.forEach(function (el, i) {
    el.addEventListener('mouseenter', function () { hi(i); });
    el.addEventListener('mouseleave', clr);
    el.addEventListener('focus', function () { hi(i); });
    el.addEventListener('click', function () { lastGraphNode = el; hi(i); open(i, false); });
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); lastGraphNode = el; hi(i); open(i, true); }
    });
  });
  var fsel = document.getElementById('g-family');
  if (fsel) fsel.addEventListener('change', function () {
    var k = fsel.value;
    nodeEls.forEach(function (el, j) {
      var off = !!k && N[j].fk !== k;
      el.classList.toggle('off', off);
      el.setAttribute('tabindex', off ? '-1' : '0');
    });
    edgeEls.forEach(function (el, j) { el.classList.toggle('off', !!k && N[E[j].s].fk !== k && N[E[j].t].fk !== k); });
  });
  var rb = document.getElementById('g-reset');
  if (rb) rb.addEventListener('click', function () { clr(); if (panel) panel.hidden = true; if (fsel) { fsel.value = ''; fsel.dispatchEvent(new Event('change')); } });
})();

/* ===================== PROMPT FINDER ===================== */
(function () {
  'use strict';
  var box = document.getElementById('findResults'); if (!box) return;
  var input = document.getElementById('findQ'), go = document.getElementById('findGo');
  var STOP = {'the':1,'a':1,'an':1,'i':1,'to':1,'my':1,'me':1,'for':1,'that':1,'with':1,'help':1,'need':1,'want':1,
    'ai':1,'prompt':1,'and':1,'or':1,'of':1,'in':1,'on':1,'is':1,'it':1,'this':1,'do':1,'get':1,'some':1,'kind':1,
    'best':1,'can':1,'you':1,'how':1,'find':1,'give':1,'good':1,'so':1,'be':1,'able':1,'use':1,'user':1,'am':1,'looking':1};
  // intent keyword -> matching family keys and/or pattern names (boosts on top of literal matches)
  var INTENT = {
    debug:{f:['debug-rootcause']}, flaky:{f:['debug-rootcause']}, intermittent:{f:['debug-rootcause']},
    bug:{f:['debug-rootcause','build-verify']}, crash:{f:['debug-rootcause']}, stack:{f:['debug-rootcause']},
    test:{f:['test-generation','build-verify']}, tests:{f:['test-generation','build-verify']}, coverage:{f:['test-generation']},
    tdd:{f:['build-verify']}, failing:{f:['build-verify','debug-rootcause']}, green:{f:['build-verify']},
    research:{f:['research-until-dry']}, market:{f:['research-until-dry']}, competitor:{f:['research-until-dry']},
    sources:{f:['research-until-dry','rag-answer']}, cited:{f:['rag-answer']}, citation:{f:['rag-answer']},
    rag:{f:['rag-answer']}, retrieval:{f:['rag-answer']}, retrieve:{f:['rag-answer']}, answer:{f:['rag-answer']},
    docs:{f:['rag-answer','structured-extraction']}, document:{f:['rag-answer','structured-extraction']},
    refactor:{f:['refactor-safe']}, migrate:{f:['migration-codemod']}, migration:{f:['migration-codemod']},
    codemod:{f:['migration-codemod']}, rename:{f:['migration-codemod']},
    image:{f:['image-generation']}, photo:{f:['image-generation']}, logo:{f:['image-generation']},
    video:{f:['video-generation']}, clip:{f:['video-generation']},
    sql:{f:['sql-analytics']}, query:{f:['sql-analytics']}, analytics:{f:['sql-analytics']}, metric:{f:['sql-analytics']},
    browser:{f:['browser-agent']}, scrape:{f:['browser-agent']}, form:{f:['browser-agent','structured-extraction']},
    login:{f:['browser-agent']}, checkout:{f:['browser-agent']}, click:{f:['browser-agent']},
    extract:{f:['structured-extraction']}, schema:{f:['structured-extraction']}, invoice:{f:['structured-extraction']},
    table:{f:['structured-extraction']}, parse:{f:['structured-extraction']},
    memory:{f:['agent-memory']}, remember:{f:['agent-memory']}, tool:{f:['tool-use']}, api:{f:['tool-use']},
    agent:{f:['multi-agent','orchestration-harness']}, supervisor:{f:['multi-agent','orchestration-harness']},
    debate:{f:['multi-agent']}, judge:{f:['multi-agent'],p:['Judge / rubric']},
    review:{f:['review-dimensions','redteam-verify']}, security:{f:['review-dimensions']},
    verify:{f:['redteam-verify'],p:['Adversarial verification']}, claim:{f:['redteam-verify']}, factcheck:{f:['redteam-verify']},
    critique:{f:['self-critique']}, revise:{f:['self-critique']}, draft:{f:['self-critique']}, edit:{f:['self-critique']},
    plan:{f:['planning-decompose']}, planning:{f:['planning-decompose']}, decompose:{f:['planning-decompose']}, breakdown:{f:['planning-decompose']},
    eval:{f:['eval-benchmark','prompt-optimization']}, benchmark:{f:['eval-benchmark']}, optimize:{f:['prompt-optimization']},
    pipeline:{f:['data-pipeline','orchestration-harness']}, etl:{f:['data-pipeline']}, parallel:{f:['orchestration-harness']},
    retry:{p:['Anti-oscillation']}, fallback:{p:['Human escalation']}, human:{p:['Human escalation']},
    approval:{p:['Human escalation']}, escalate:{p:['Human escalation']}, deterministic:{p:['Mechanical verifier']}
  };
  var DATA = null;
  function tokens(q) {
    return (q.toLowerCase().match(/[a-z0-9]+/g) || []).filter(function (t) { return t.length > 1 && !STOP[t]; });
  }
  var esc = pesc;
  function scoreOf(p, ts) {
    var s = 0, why = { terms: {}, fam: false, pats: {} };
    var t1 = (p.title + ' ' + (p.full_title || '') + ' ' + (p.alt || '')).toLowerCase();
    var w = (p.when || '').toLowerCase(), f = (p.family_title || '').toLowerCase();
    var pats = (p.patterns || []).join(' | ').toLowerCase(), body = (p.prompt_text || '').toLowerCase();
    ts.forEach(function (t) {
      if (t1.indexOf(t) >= 0) { s += 6; why.terms[t] = 1; }
      if (w.indexOf(t) >= 0) { s += 4; why.terms[t] = 1; }
      if (f.indexOf(t) >= 0) { s += 3; why.fam = true; }
      if (pats.indexOf(t) >= 0) { s += 2; }
      if (body.indexOf(t) >= 0) { s += 1; }
      // intent boost
      for (var key in INTENT) {
        if (t === key || (t.length > 3 && key.indexOf(t) === 0) || (key.length > 3 && t.indexOf(key) === 0)) {
          var m = INTENT[key];
          if (m.f && m.f.indexOf(p.family_key) >= 0) { s += 5; why.fam = true; }
          if (m.p) m.p.forEach(function (pn) { if ((p.patterns || []).indexOf(pn) >= 0) { s += 3; why.pats[pn] = 1; } });
        }
      }
    });
    if (p.starter) s += 0.6;
    return { s: s, why: why };
  }
  function render(list, q) {
    if (!q) { box.innerHTML = ''; return; }
    if (!list.length) {
      box.innerHTML = '<p class="find-empty">No strong match. Try different words (a task verb like “debug”, “research”, “extract”), or <a href="library.html">browse the library</a>.</p>';
      return;
    }
    var top = list[0];
    function whyText(r) {
      var bits = [];
      var terms = Object.keys(r.res.why.terms); if (terms.length) bits.push('matches <strong>' + terms.map(esc).join(', ') + '</strong>');
      if (r.res.why.fam) bits.push('right family (' + esc(r.p.family_title) + ')');
      var pats = Object.keys(r.res.why.pats); if (pats.length) bits.push('has ' + pats.map(esc).join(', '));
      return bits.join(' · ') || 'partial keyword overlap';
    }
    function card(r, best) {
      var p = r.p;
      return '<a class="find-card' + (best ? ' find-best' : '') + '" href="prompt/' + p.id + '.html">' +
        (best ? '<span class="find-badge">Best match</span>' : '') +
        '<span class="pcard-fam">' + esc(p.family_title) + '</span>' +
        '<span class="find-title">' + esc(p.title) + '</span>' +
        '<span class="find-when">' + esc((p.when || '').slice(0, 130)) + '…</span>' +
        '<span class="find-why">' + whyText(r) + '</span></a>';
    }
    box.innerHTML = '<p class="find-count">Top ' + list.length + ' of ' + DATA.length + ' — best fit first.</p>' +
      '<div class="find-best-wrap">' + card(top, true) + '</div>' +
      '<div class="pcard-grid">' + list.slice(1).map(function (r) { return card(r, false); }).join('') + '</div>';
  }
  function run() {
    var q = (input.value || '').trim(); if (!DATA) return;
    var ts = tokens(q);
    if (!ts.length) { render([], ''); return; }
    var scored = DATA.map(function (p) { return { p: p, res: scoreOf(p, ts) }; })
      .filter(function (r) { return r.res.s > 0; })
      .sort(function (a, b) { return b.res.s - a.res.s; }).slice(0, 6);
    render(scored, q);
  }
  fetch('data/prompts.json').then(function (r) { return r.json(); }).then(function (d) {
    DATA = d;
    go.addEventListener('click', run);
    input.addEventListener('keydown', function (e) { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') run(); });
    [].slice.call(document.querySelectorAll('.find-ex')).forEach(function (b) {
      b.addEventListener('click', function () { input.value = b.getAttribute('data-q'); run(); input.focus(); });
    });
    // deep-link: ?q=... (e.g. from the home hero)
    var m = location.search.match(/[?&]q=([^&]+)/);
    if (m) { input.value = decodeURIComponent(m[1].replace(/\+/g, ' ')); run(); }
  });
})();

/* ===================== ANALYSIS ENGINE (client mirror of build_site.py) =====================
   Reads window.PROMPTOS_RULES (rule tables emitted from the Python engine) so /lab and
   /compare classify arbitrary pasted text with the SAME rules the site was built with. */
var PROMPTOS = (function () {
  var R = window.PROMPTOS_RULES;
  if (!R) return null;
  try {
  var esc = pesc;
  var EXPL = new RegExp(R.explicitVerifier, 'i');
  function explicitVerifier(t){var m=t.match(EXPL);return m?m[1].trim():'';}
  var KWB = R.keywordBoundary || '(^|[^a-z0-9])';
  var _kwCache = {};
  function kwHit(blob, k){
    var re = _kwCache[k] || (_kwCache[k] = new RegExp(KWB + k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    return re.test(blob);
  }
  function deriveVerifier(text, model){
    var explicit=explicitVerifier(text);
    var blob=((model||'')+' '+(explicit||text)).toLowerCase();
    var mech=R.mechKw.some(function(k){return kwHit(blob,k);});
    var judge=R.judgeKw.some(function(k){return kwHit(blob,k);});
    if(mech&&!judge)return 'mechanical';
    if(judge&&!mech)return 'judge';
    if(mech&&judge)return 'mixed';
    if(explicit)return 'mechanical';
    return 'unspecified';
  }
  var ANCHORS=R.anchors.map(function(a){return [a[0], new RegExp(a[1],'gi')];});
  function segmentAnatomy(text){
    text=text.trim();
    var hits=[], i, a, m;
    for(i=0;i<ANCHORS.length;i++){a=ANCHORS[i];a[1].lastIndex=0;while((m=a[1].exec(text))){hits.push([m.index,a[0]]);if(m.index===a[1].lastIndex)a[1].lastIndex++;}}
    hits.sort(function(x,y){return x[0]-y[0]||(x[1]<y[1]?-1:x[1]>y[1]?1:0);});
    var cleaned=[];
    for(i=0;i<hits.length;i++){if(cleaned.length&&hits[i][0]-cleaned[cleaned.length-1][0]<3)continue;cleaned.push(hits[i]);}
    if(!cleaned.length)return [['goal',text]];
    var segs=[];
    if(cleaned[0][0]>0){var lead=text.slice(0,cleaned[0][0]).trim();if(lead)segs.push(['goal',lead]);}
    for(i=0;i<cleaned.length;i++){var end=i+1<cleaned.length?cleaned[i+1][0]:text.length;var seg=text.slice(cleaned[i][0],end).trim();if(seg)segs.push([cleaned[i][1],seg]);}
    var merged=[];
    for(i=0;i<segs.length;i++){if(merged.length&&merged[merged.length-1][0]===segs[i][0])merged[merged.length-1][1]+=' '+segs[i][1];else merged.push([segs[i][0],segs[i][1]]);}
    return merged;
  }
  function has(low){for(var i=1;i<arguments.length;i++)if(low.indexOf(arguments[i])>=0)return true;return false;}
  function detectPatterns(text, verifier, fk){
    var low=text.toLowerCase(), f=new Set();
    if(low.indexOf('commit')>=0&&(has(low,'git reset','revert','discard')))f.add('commit-revert');
    if(has(low,'never repeat','different approach','materially different','never the identical','not a re-tuned','not a retuned','oscillat'))f.add('anti-oscillation');
    if(has(low,'escalate','hand off','hand it off','request human','needs a human','human can make','only a human','wait for a human'))f.add('human-escalation');
    if(has(low,'do not edit',"don't edit",'off-limits',"while i'm here",'do not adopt',"don't refactor",'scope is','park those',"don't loosen","don't hand-tune",'not the moment'))f.add('freeze-scope');
    if(verifier==='mechanical')f.add('mechanical-verifier');
    if(verifier==='judge')f.add('judge-rubric');
    if(fk==='redteam-verify'||has(low,'adversarial','refute','skeptic','red team','red-team'))f.add('adversarial-verify');
    if(low.indexOf('regression')>=0&&has(low,'regression test','failing test','reproduce','frozen'))f.add('regression-first');
    if(fk==='research-until-dry'||has(low,'dry counter','stale counter','saturat','no new'))f.add('research-saturation');
    if(has(low,'fan-out','fan out','subagent','sub-agent','in parallel','parallelize'))f.add('fan-out');
    if(low.indexOf('pipeline')>=0||(low.indexOf('stage')>=0&&has(low,'stage 1','each stage','stages'))){if(low.indexOf('pipeline')>=0||low.indexOf('stages')>=0)f.add('pipeline');}
    if(has(low,'ratchet','strictness','per-file error','error count','error-count'))f.add('ratchet');
    if(low.indexOf('characterization')>=0)f.add('characterization-test');
    if(fk==='migration-codemod'||has(low,'worklist','codemod','call-site','call site'))f.add('worklist-codemod');
    if(has(low,'shadow','expand-migrate-contract','expand, migrate','dual-write','dual write','shadow-read'))f.add('shadow-verify');
    return f;
  }
  function parseStopArms(text){
    var re=/\b(SUCCESS|BUDGET|NO-PROGRESS|BLOCKED)\b/g, hits=[], m;
    while((m=re.exec(text)))hits.push([m.index,m.index+m[1].length,m[1]]);
    var arms={};
    for(var i=0;i<hits.length;i++){var nxt=i+1<hits.length?hits[i+1][0]:text.length;var d=text.slice(hits[i][1],nxt).replace(/^[\s:：—–\-·|]+/,'').trim();arms[hits[i][2]]=d;}
    return arms;
  }
  function variables(text){var m=text.match(/<[^>\n]{1,50}>/g)||[];return Array.from(new Set(m)).sort();}
  function complexity(text, patCount, varCount){
    var steps=(text.match(/\(\d+\)/g)||[]).length;
    var decisions=(text.match(/\bif\b/gi)||[]).length;
    var nested=(text.match(/\([a-e]\)/g)||[]).length;
    var arms=Object.keys(parseStopArms(text)).length;
    var score=steps+patCount+decisions+nested+Math.floor(varCount/2);
    return {steps:steps,stop_arms:arms,variables:varCount,decisions:decisions,patterns:patCount,nested:nested,chars:text.length,
            band:score<10?'compact':score<16?'standard':'dense'};
  }
  function shortq(s,n){s=s.replace(/\s+/g,' ').trim();s=s.replace(/^(GOAL \(frozen\)|Goal \(frozen\)|GOAL|Goal|VERIFIER|Verifier|Carry forward[^:]*|LOOP \([^)]*\)|Turn shape)\s*[:.]?\s*/,'');if(s.length>n)s=s.slice(0,n).replace(/\s+\S*$/,'')+'…';return esc(s);}
  function find1(text,re){var m=text.match(re);return m?m[1]:null;}
  function whyPoints(text, verifier, fk){
    var low=text.toLowerCase(), segs=segmentAnatomy(text), roles=new Set(segs.map(function(s){return s[0];})), pts=[];
    var goalSeg=(segs.find(function(s){return s[0]==='goal';})||[null,text])[1];
    pts.push(['Anchor to a measurable, frozen goal','goal','“'+shortq(goalSeg,190)+'”']);
    var vclause=find1(text,/(verified by [^.;]+|as (?:your|the) verifier[^.;]*|VERIFIER:[^.;]+|independent check[^.;]*|independent(?:ly)? (?:verified|corroborat)[^.;]*)/i);
    var vtxt=(verifier==='mechanical'||verifier==='judge'||verifier==='mixed')?'Verifier here is <strong>'+verifier+'</strong>. ':'';
    vtxt+=vclause?'“'+shortq(vclause,150)+'”':'the mechanism that decides “done” is separate from what’s being changed.';
    pts.push(['Verify with an independent signal, not self-assessment','verifier',vtxt]);
    if(roles.has('action')||/\bONE\b/.test(text)){var a=find1(text,/(make (?:the )?(?:smallest|one)[^.;]+|exactly ONE[^.;]+|ONE (?:reversible |source |transform |resource |optimization |handler[- ]behavior )?[^.;]+)/i);if(a)pts.push(['One reversible action per turn, then observe','action','“'+shortq(a,150)+'”']);}
    if(low.indexOf('commit')>=0&&(low.indexOf('git reset')>=0||low.indexOf('revert')>=0||low.indexOf('discard')>=0))pts.push(['Preserve a known-good workspace each turn',null,'Commit on improvement, revert on regression — a bad turn can’t corrupt the baseline.']);
    if(roles.has('state')){var s=(segs.find(function(x){return x[0]==='state';})||[null,''])[1];pts.push(['Carry compact state across turns','state','“'+shortq(s,160)+'”']);}
    if(/never repeat|different approach|materially different|don't keep grinding|oscillat|never the identical|never retry the identical|not a re-?tuned/.test(low)){var n=find1(text,/([^.;]*?(?:never repeat|different approach|materially different|don't keep grinding|oscillat|never the identical|never retry the identical|not a re-?tuned)[^.;]*)/i);pts.push(['Detect and break non-progress and oscillation',null,n?'“'+shortq(n,150)+'”':'A retry must change approach, not re-attempt the same thing.']);}
    if(/do not edit|don't edit|off-limits|while i'm here|do not adopt|not the moment|scope is|don't loosen|park those|don't redesign|don't hand-tune|don't refactor/.test(low)){var fscope=find1(text,/([^.;]*?(?:do not edit|don't edit|off-limits|while I'm here|do not adopt|not the moment|scope is|don't loosen|park those|don't redesign|don't hand-tune|don't refactor)[^.;]*)/i);pts.push(['Freeze scope and ban gold-plating',null,fscope?'“'+shortq(fscope,150)+'”':'The loop closes the defined gap and nothing else.']);}
    if(fk==='research-until-dry'||low.indexOf('dry counter')>=0||low.indexOf('stale counter')>=0||low.indexOf('saturat')>=0)pts.push(['For research loops, define saturation (‘dry’)',null,'It stops when new sources stop changing the answer — evidence-saturated, not effort-exhausted.']);
    if(/escalate|hand off|hand it off|request human|needs a human|human can make|only a human|wait for a human/.test(low))pts.push(['Fail loud after repeated failure; escalate, don’t grind',null,'When progress stalls or a call needs a human, it halts and surfaces what was tried.']);
    return pts;
  }
  // ---- analysis object + renderers ----
  var STOP_CLASS={SUCCESS:'arm-success',BUDGET:'arm-budget','NO-PROGRESS':'arm-noprogress',BLOCKED:'arm-blocked'};
  function highlight(escaped, role){
    if(role==='stop')return escaped.replace(/\b(SUCCESS|BUDGET|NO-PROGRESS|BLOCKED)\b/g,function(m,g){return '<span class="'+STOP_CLASS[g]+'">'+g+'</span>';});
    if(role==='action'||role==='context'||role==='verifier')return escaped.replace(/\b(independent verifier|as the verifier|as your verifier|as verifier|independent check|verifier|verify)\b|\b(git reset|commit|revert)\b/gi,function(m,v){return v?'<span class="hl-verify">'+m+'</span>':'<span class="hl-invariant">'+m+'</span>';});
    return escaped;
  }
  var PNAME={}, PROLE={}; R.patternMeta.forEach(function(p){PNAME[p[0]]=p[1];PROLE[p[0]]=p[2];});
  function analyze(text, opts){
    opts=opts||{}; text=(text||'').trim();
    var fk=opts.fk||'', model=opts.model||'';
    var verifier=deriveVerifier(text,model);
    var pats=Array.from(detectPatterns(text,verifier,fk));
    var patsOrdered=R.patternMeta.map(function(p){return p[0];}).filter(function(k){return pats.indexOf(k)>=0;});
    var vars=variables(text);
    var cx=complexity(text,patsOrdered.length,vars.length);
    return {text:text,roles:segmentAnatomy(text),verifier:verifier,patterns:patsOrdered,
            complexity:cx,why:whyPoints(text,verifier,fk),stopArms:parseStopArms(text),variables:vars};
  }
  function anatomyHTML(roles){
    return roles.map(function(rs){var e=highlight(esc(rs[1]),rs[0]).replace(/\n/g,'<br>');
      return '<div class="anat anat-'+rs[0]+'"><span class="anat-label">'+esc(R.anatLabels[rs[0]])+'</span><div class="anat-body">'+e+'</div></div>';}).join('');
  }
  function patternChipsHTML(keys,prefix){
    if(!keys.length)return '<p class="muted">No discriminating patterns detected.</p>';
    return keys.map(function(k){return '<a class="chip chip-pattern" href="'+(prefix||'')+'pattern/'+k+'.html">'+esc(PNAME[k])+'</a>';}).join('');
  }
  function verifierBadgeHTML(v){
    var d={mechanical:'execution / ground-truth signal',judge:'model / rubric judgment',mixed:'both mechanical and judged',unspecified:'no clear independent verifier detected'};
    return '<span class="chip chip-verifier chip-'+(v==='unspecified'?'none':v)+'">'+v+' verifier</span><span class="muted"> — '+d[v]+'</span>';
  }
  function complexityHTML(cx){
    var items=[['steps',cx.steps],['stop arms',cx.stop_arms],['patterns',cx.patterns],['variables',cx.variables],['decisions',cx.decisions]];
    return '<div class="cx"><span class="cx-band cx-'+cx.band+'">'+cx.band+' structure</span>'+items.map(function(it){return '<span class="cx-item"><b>'+it[1]+'</b> '+it[0]+'</span>';}).join('')+'</div>';
  }
  function whyHTML(why){
    return '<ul class="why-list">'+why.map(function(w){var dot=w[1]?'<span class="why-dot anat-dot-'+w[1]+'"></span>':'<span class="why-dot why-dot-plain"></span>';return '<li>'+dot+'<div class="why-text"><strong>'+esc(w[0])+'.</strong> <span class="why-ev">'+w[2]+'</span></div></li>';}).join('')+'</ul>';
  }
  function stopArmsHTML(arms){
    var order=[['SUCCESS','arm-success'],['BUDGET','arm-budget'],['NO-PROGRESS','arm-noprogress'],['BLOCKED','arm-blocked']], rows='';
    order.forEach(function(o){if(arms[o[0]]!==undefined)rows+='<div class="stoparm '+o[1]+'"><span class="arm-name">'+o[0]+'</span><span class="arm-body">'+esc(arms[o[0]])+'</span></div>';});
    return rows?'<div class="stoparms">'+rows+'</div>':'';
  }
  function flagsHTML(a){
    var flags=[], have=new Set(a.roles.map(function(r){return r[0];}));
    if(a.verifier==='unspecified'&&!have.has('verifier'))flags.push('No <strong>independent verifier</strong> named — the loop may end up grading its own work.');
    if(!Object.keys(a.stopArms).length)flags.push('No explicit <strong>stop condition</strong> (SUCCESS / BUDGET / NO-PROGRESS / BLOCKED) — a loop with no exit can run forever.');
    if(!have.has('goal')&&a.roles.length)flags.push('No clearly <strong>frozen goal</strong> up front.');
    if(!flags.length)return '';
    return '<div class="lab-flags"><span class="lab-flags-h">⚠ Missing loop structure</span><ul>'+flags.map(function(f){return '<li>'+f+'</li>';}).join('')+'</ul></div>';
  }
  return {analyze:analyze,esc:esc,anatomyHTML:anatomyHTML,patternChipsHTML:patternChipsHTML,verifierBadgeHTML:verifierBadgeHTML,
          complexityHTML:complexityHTML,whyHTML:whyHTML,stopArmsHTML:stopArmsHTML,flagsHTML:flagsHTML,anatLabels:R.anatLabels,anatOrder:R.anatOrder,PNAME:PNAME};
  } catch (e) {
    /* A rule regex valid in Python but not in JS used to throw here at module scope,
       aborting the rest of app.js on all 261 pages. Fail soft instead. */
    if (window.console) console.error('prompt-os: analysis engine disabled —', e && e.message);
    return null;
  }
})();

/* ===================== LAB (analyze your own prompt) ===================== */
(function () {
  if (!PROMPTOS) return;
  var input=document.getElementById('labInput'); if(!input) return;
  var go=document.getElementById('labGo'), clear=document.getElementById('labClear'),
      box=document.getElementById('labResults'), legend=document.querySelector('.lab-legend'),
      rw=document.getElementById('labRewrite'), rwBtn=document.getElementById('labRewriteBtn'),
      rwOut=document.getElementById('labRewriteOut');
  var EX={}, cur=null;
  function render(a){
    cur=a;
    if(rw){rw.hidden=!a.text;} if(rwOut){rwOut.innerHTML='';}
    if(!a.text){box.innerHTML='<p class="lab-empty muted">Paste a prompt above, then Analyze.</p>';if(legend)legend.hidden=true;return;}
    if(legend)legend.hidden=false;
    var html=''+
      '<div class="lab-summary">'+PROMPTOS.verifierBadgeHTML(a.verifier)+'</div>'+
      PROMPTOS.flagsHTML(a)+
      '<div class="patternrow"><span class="patternrow-label">Patterns</span>'+PROMPTOS.patternChipsHTML(a.patterns,'')+'</div>'+
      PROMPTOS.complexityHTML(a.complexity)+
      (a.variables.length?'<div class="vars"><span class="vars-label">Placeholders:</span> '+a.variables.map(function(v){return '<code class="var">'+PROMPTOS.esc(v)+'</code>';}).join(' ')+'</div>':'')+
      '<h2 class="sub">Loop anatomy</h2><div class="anat-wrap">'+PROMPTOS.anatomyHTML(a.roles)+'</div>'+
      '<h2 class="sub">Why it works (from your text)</h2>'+PROMPTOS.whyHTML(a.why)+
      (Object.keys(a.stopArms).length?'<h2 class="sub">The four exits</h2>'+PROMPTOS.stopArmsHTML(a.stopArms):'');
    box.innerHTML=html;
    box.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
  // deterministic scaffold: the canonical loop shape with the user's own content
  // slotted in and every gap marked <FILL: …>. No LLM, no network.
  function scaffoldText(a){
    var have={}; a.roles.forEach(function(r){have[r[0]]=1;});
    var goalSeg=(a.roles.filter(function(r){return r[0]==='goal';})[0]||[null,a.text])[1];
    var goal=goalSeg.replace(/\s+/g,' ').trim(); if(goal.length>280) goal=goal.slice(0,280).replace(/\s+\S*$/,'')+' …';
    var vLine=(a.verifier==='unspecified'||!have.verifier)
      ? '<FILL: name an INDEPENDENT verifier — a check separate from whatever makes the change (a test suite, a scanner/linter, a benchmark, a schema validator, or a rubric/judge in a fresh frame). It must be able to return "not done" and must never grade its own output.>'
      : 'Decide "done" with your '+a.verifier+' signal, run as a step separate from the action — it must not grade its own output.';
    var arms=a.stopArms||{};
    function arm(n,fb){ return (arms[n]&&arms[n].length>2)?arms[n]:'<FILL: '+fb+'>'; }
    return 'GOAL (frozen — do not redefine mid-loop)\n'+goal+'\n\n'+
      'INDEPENDENT VERIFIER\n'+vLine+'\n\n'+
      'PER-TURN SHAPE\n'+
      '1. ASSESS — compare the current state to the goal; choose the ONE next action.\n'+
      '2. ONE ACTION — make exactly one small, reversible change.\n'+
      '3. VERIFY — run the independent verifier above; trust its result, not your own confidence.\n'+
      '4. DECIDE — commit on a verified improvement, revert on regression, otherwise escalate.\n\n'+
      'CARRY-FORWARD STATE (compact)\n'+
      'Goal, what has been tried, current best, last verifier result, remaining budget.\n\n'+
      'ACTION BAN\n'+
      'Never grade your own work; never repeat a failed action verbatim (change approach); never widen the goal or weaken the check to declare victory.\n\n'+
      'STOP — halt on the FIRST of:\n'+
      'SUCCESS ('+arm('SUCCESS','goal met and independently verified')+') | BUDGET ('+arm('BUDGET','max turns / tokens / wall-clock reached')+') | NO-PROGRESS ('+arm('NO-PROGRESS','the metric has not improved for K turns, or it oscillates A->B->A')+') | BLOCKED ('+arm('BLOCKED','needs a human decision or an unavailable resource')+')';
  }
  function doRewrite(){
    if(!cur||!cur.text) return;
    var have={}; cur.roles.forEach(function(r){have[r[0]]=1;});
    var kept=[], fill=[];
    if(have.goal) kept.push('your goal'); else fill.push('a frozen goal');
    if(cur.verifier!=='unspecified'&&have.verifier) kept.push('your '+cur.verifier+' verifier'); else fill.push('an independent verifier');
    var na=Object.keys(cur.stopArms||{}).length;
    if(na>=4) kept.push('all 4 stop arms'); else if(na>0) { kept.push(na+' of 4 stop arms'); fill.push((4-na)+' more stop arm'+(4-na===1?'':'s')); } else fill.push('the 4 stop arms');
    var txt=scaffoldText(cur);
    rwOut.innerHTML=''+
      '<p class="lab-rewrite-note">A scaffold from your prompt'+(kept.length?' — <strong>kept:</strong> '+kept.join(', '):'')+
      (fill.length?'. <strong>Fill</strong> the <code>&lt;FILL: …&gt;</code> gaps for: '+fill.join(', '):'')+'.</p>'+
      '<div class="prompt-toolbar"><button class="btn btn-primary" id="labScaffoldCopy" type="button">Copy scaffold</button></div>'+
      '<pre class="promptbody" id="labScaffold">'+PROMPTOS.esc(txt)+'</pre>';
    var cb=document.getElementById('labScaffoldCopy');
    cb.addEventListener('click',function(){ try{navigator.clipboard.writeText(txt);}catch(e){} cb.textContent='Copied ✓'; setTimeout(function(){cb.textContent='Copy scaffold';},1500); });
    rwOut.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
  if(rwBtn) rwBtn.addEventListener('click',doRewrite);
  function run(){render(PROMPTOS.analyze(input.value,{}));}
  go.addEventListener('click',run);
  input.addEventListener('keydown',function(e){if((e.metaKey||e.ctrlKey)&&e.key==='Enter')run();});
  clear.addEventListener('click',function(){input.value='';box.innerHTML='';if(legend)legend.hidden=true;if(rw)rw.hidden=true;if(rwOut)rwOut.innerHTML='';cur=null;input.focus();});
  // examples: load real corpus prompt text (with its family_key so patterns match the detail page exactly)
  var exBtns=[].slice.call(document.querySelectorAll('.lab-ex'));
  if(exBtns.length){
    fetch('data/prompts.json').then(function(r){return r.json();}).then(function(d){
      d.forEach(function(p){EX[p.id]=p;});
      exBtns.forEach(function(b){b.addEventListener('click',function(){var p=EX[b.getAttribute('data-id')];if(!p)return;input.value=p.prompt_text;render(PROMPTOS.analyze(p.prompt_text,{fk:p.family_key,model:p.model}));});});
    });
  }
})();

/* ===================== SKILL EXPORT (prompt detail -> Claude Code skill file) ===================== */
(function () {
  var s = window.__SKILL__, btn = document.getElementById('skillExport');
  if (!s || !btn) return;
  function md(){
    var desc = (s.when||'').replace(/\s+/g,' ').trim();
    if (desc.length>240) desc = desc.slice(0,240).replace(/\s+\S*$/,'')+'…';
    return '---\n'+
      'name: '+s.name+'\n'+
      'description: '+desc+'\n'+
      '---\n\n'+
      '# '+s.title+'\n\n'+
      'Use this agent-loop when: '+(s.when||'')+'\n\n'+
      'Run it as a bounded loop — follow the prompt below exactly, and fill every <PLACEHOLDER> before you start:\n\n'+
      s.body+'\n\n'+
      '---\n'+
      'Model routing: '+(s.model||'—')+'\n'+
      'Source: prompt-os loop library — family "'+s.family+'", prompt '+s.name+'. MIT licensed.\n';
  }
  btn.addEventListener('click', function(){
    try {
      var blob = new Blob([md()], {type:'text/markdown'});
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url; a.download = s.name+'.md';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function(){ URL.revokeObjectURL(url); }, 1000);
      btn.textContent = 'Downloaded ✓';
    } catch(e){
      try { navigator.clipboard.writeText(md()); btn.textContent='Copied ✓ (save as SKILL.md)'; } catch(e2){}
    }
    setTimeout(function(){ btn.textContent='⤓ Export as Claude Code skill'; }, 1800);
  });
})();

/* ===================== COMPARE (two prompts side by side) ===================== */
(function () {
  if (!PROMPTOS) return;
  var selA=document.getElementById('cmpSelA'); if(!selA) return;
  var selB=document.getElementById('cmpSelB'), taA=document.getElementById('cmpTextA'), taB=document.getElementById('cmpTextB'),
      go=document.getElementById('cmpGo'), diffBox=document.getElementById('cmpDiff'), resBox=document.getElementById('cmpResults');
  var BY={};
  function colHTML(a,label){
    return '<div class="cmp-col"><h3 class="cmp-col-h">'+label+'</h3>'+
      '<div class="lab-summary">'+PROMPTOS.verifierBadgeHTML(a.verifier)+'</div>'+
      '<div class="patternrow"><span class="patternrow-label">Patterns</span>'+PROMPTOS.patternChipsHTML(a.patterns,'')+'</div>'+
      PROMPTOS.complexityHTML(a.complexity)+
      '<h4 class="sub">Anatomy</h4><div class="anat-wrap">'+PROMPTOS.anatomyHTML(a.roles)+'</div>'+
      (Object.keys(a.stopArms).length?'<h4 class="sub">Exits</h4>'+PROMPTOS.stopArmsHTML(a.stopArms):'')+'</div>';
  }
  function diffHTML(a,b){
    var sa=new Set(a.patterns), sb=new Set(b.patterns);
    var shared=a.patterns.filter(function(k){return sb.has(k);});
    var onlyA=a.patterns.filter(function(k){return !sb.has(k);});
    var onlyB=b.patterns.filter(function(k){return !sa.has(k);});
    function names(ks){return ks.length?ks.map(function(k){return '<span class="chip chip-pattern">'+PROMPTOS.esc(PROMPTOS.PNAME[k])+'</span>';}).join(''):'<span class="muted">none</span>';}
    var rows=''+
      '<div class="cmp-diff-row"><span class="cmp-diff-k">Verifier</span><span>'+a.verifier+(a.verifier===b.verifier?' <span class="muted">(same)</span>':' <span class="cmp-vs">vs</span> '+b.verifier)+'</span></div>'+
      '<div class="cmp-diff-row"><span class="cmp-diff-k">Complexity</span><span>'+a.complexity.band+(a.complexity.band===b.complexity.band?' <span class="muted">(same)</span>':' <span class="cmp-vs">vs</span> '+b.complexity.band)+'</span></div>'+
      '<div class="cmp-diff-row"><span class="cmp-diff-k">Shared patterns</span><span>'+names(shared)+'</span></div>'+
      '<div class="cmp-diff-row"><span class="cmp-diff-k">Only in A</span><span>'+names(onlyA)+'</span></div>'+
      '<div class="cmp-diff-row"><span class="cmp-diff-k">Only in B</span><span>'+names(onlyB)+'</span></div>';
    return '<div class="cmp-diff-card"><h2 class="section-h">What differs</h2>'+rows+'</div>';
  }
  function getSide(sel,ta){
    var txt=(ta.value||'').trim();
    if(txt)return PROMPTOS.analyze(txt,{});
    var p=BY[sel.value]; if(!p)return null;
    return PROMPTOS.analyze(p.prompt_text,{fk:p.family_key,model:p.model});
  }
  function run(){
    var a=getSide(selA,taA), b=getSide(selB,taB);
    if(!a||!b){resBox.innerHTML='<p class="muted">Pick a prompt (or paste one) on both sides.</p>';diffBox.innerHTML='';return;}
    diffBox.innerHTML=diffHTML(a,b);
    resBox.innerHTML='<div class="cmp-grid">'+colHTML(a,PROMPTOS.esc(taA.value.trim()?'Prompt A (pasted)':(BY[selA.value]?BY[selA.value].title:'Prompt A')))+colHTML(b,PROMPTOS.esc(taB.value.trim()?'Prompt B (pasted)':(BY[selB.value]?BY[selB.value].title:'Prompt B')))+'</div>';
  }
  go.addEventListener('click',run);
  fetch('data/prompts.json').then(function(r){return r.json();}).then(function(d){
    d.sort(function(x,y){return x.family_title<y.family_title?-1:x.family_title>y.family_title?1:(x.title<y.title?-1:1);});
    var opts='';
    d.forEach(function(p){BY[p.id]=p;opts+='<option value="'+p.id+'">'+PROMPTOS.esc(p.family_title+' — '+p.title)+'</option>';});
    selA.innerHTML+=opts; selB.innerHTML+=opts;
    // sensible defaults: two different prompts
    if(d.length>1){selA.value=d[0].id;selB.value=d[Math.min(1,d.length-1)].id;
      var qa=location.search.match(/[?&]a=([^&]+)/), qb=location.search.match(/[?&]b=([^&]+)/);
      if(qa&&BY[decodeURIComponent(qa[1])])selA.value=decodeURIComponent(qa[1]);
      if(qb&&BY[decodeURIComponent(qb[1])])selB.value=decodeURIComponent(qb[1]);
      run();}
  });
})();

/* ===================== LEARN (course progress + quizzes) ===================== */
(function () {
  var page = document.querySelector('.learn-page'); if (!page) return;
  var KEY = 'promptos_learn_v2';
  var lessons = [].slice.call(page.querySelectorAll('.lesson'));
  var total = lessons.length;
  var fill = document.getElementById('learnFill'), count = document.getElementById('learnCount'),
      levelEl = document.getElementById('learnLevel'), resetBtn = document.getElementById('learnReset');
  function load(){ try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch(e){ return {}; } }
  function save(){ try { localStorage.setItem(KEY, JSON.stringify(state)); } catch(e){} }
  var state = load();   // { id: {core:bool, stretch:bool} }

  function mastered(){ return lessons.filter(function(l){ var s=state[l.getAttribute('data-lesson')]; return s && s.stretch===true; }).length; }
  function levelName(m){ return m>=5 ? 'Expert' : m>=2 ? 'Practitioner' : 'Foundations'; }
  function done(){ return lessons.filter(function(l){ var s=state[l.getAttribute('data-lesson')]; return s && typeof s.core!=='undefined'; }).length; }

  function revealAnswer(quiz){ if(!quiz) return;
    var ci = parseInt(quiz.getAttribute('data-correct'),10);
    [].slice.call(quiz.querySelectorAll('.quiz-opt')).forEach(function(o){
      o.disabled = true;
      if (parseInt(o.getAttribute('data-i'),10)===ci){ o.classList.add('is-answer');
        if(!o.querySelector('.mark')){var m=document.createElement('span');m.className='mark';m.textContent='✓';o.appendChild(m);} }
    });
    var ex = quiz.querySelector('.quiz-explain'); if(ex) ex.hidden=false;
  }
  function unlockStretch(lesson){ var s=lesson.querySelector('.quiz-stretch'); if(s) s.hidden=false; }
  function showRemedial(lesson){ var r=lesson.querySelector('.quiz-remedial'); if(r) r.hidden=false; }
  function markDone(lesson){ lesson.classList.add('done'); var b=lesson.querySelector('.lesson-done'); if(b){b.hidden=false;b.removeAttribute('aria-hidden');} }
  function markMastered(lesson){ lesson.classList.add('mastered'); var b=lesson.querySelector('.lesson-mastered'); if(b){b.hidden=false;b.removeAttribute('aria-hidden');} }

  function progress(){
    var d=done(), m=mastered();
    if(fill) fill.style.width = (total?Math.round(d/total*100):0)+'%';
    if(count) count.textContent = d+' of '+total+' checks'+(d===total&&total?' — nicely done.':'');
    if(levelEl) levelEl.textContent = 'Level: '+levelName(m)+(m?' ('+m+' mastered)':'');
    if(resetBtn) resetBtn.hidden = (d===0 && m===0);
    if(m>=2) lessons.forEach(unlockStretch);   // adaptive: Practitioner+ unlocks the harder questions everywhere
  }

  function wireQuiz(lesson, quiz, kind){
    if(!quiz) return;
    var ci = parseInt(quiz.getAttribute('data-correct'),10);
    [].slice.call(quiz.querySelectorAll('.quiz-opt')).forEach(function(o){
      o.addEventListener('click', function(){
        if(o.disabled) return;
        var ok = parseInt(o.getAttribute('data-i'),10)===ci;
        o.classList.add(ok?'correct':'wrong');
        revealAnswer(quiz);
        var id = lesson.getAttribute('data-lesson'); state[id] = state[id] || {};
        if(kind==='core'){ state[id].core = ok; markDone(lesson);
          if(ok) unlockStretch(lesson); else showRemedial(lesson); }
        else { state[id].stretch = ok; if(ok) markMastered(lesson); }
        save(); progress();
      });
    });
  }
  function replay(lesson, s){
    var core = lesson.querySelector('.quiz-core'), stretch = lesson.querySelector('.quiz-stretch');
    if(typeof s.core!=='undefined'){ revealAnswer(core); markDone(lesson);
      if(s.core) unlockStretch(lesson); else showRemedial(lesson); }
    if(typeof s.stretch!=='undefined'){ unlockStretch(lesson); revealAnswer(stretch); if(s.stretch) markMastered(lesson); }
  }
  lessons.forEach(function(lesson){
    var s = state[lesson.getAttribute('data-lesson')];
    if(s) replay(lesson, s);
    if(!s || typeof s.core==='undefined') wireQuiz(lesson, lesson.querySelector('.quiz-core'), 'core');
    if(!s || typeof s.stretch==='undefined') wireQuiz(lesson, lesson.querySelector('.quiz-stretch'), 'stretch');
  });
  if(resetBtn) resetBtn.addEventListener('click', function(){ try{localStorage.removeItem(KEY);}catch(e){} location.reload(); });
  progress();
})();

/* ===================== HERO 3D LOOP (raw WebGL, zero deps) =====================
   A glowing 3D loop ring that ASSEMBLES from scattered particles on load
   (formation), then rotates slowly with a comet pulse orbiting it, an ambient
   dust field (cool + violet + a few warm-ember motes), per-node "breathing", and
   a cursor-parallax tilt. Multi-layer additive glow over the CSS deep-space
   gradient. Falls back to the static SVG ring for no-WebGL / reduced-motion /
   no-JS. Pauses when offscreen or the tab is hidden. Palette + interaction values
   are from the design research (easeOutCubic formation, lerp 0.07 cursor). */
(function () {
  var canvas = document.getElementById('heroGL'); if (!canvas) return;
  var fallback = document.getElementById('heroFallback'), viz = document.getElementById('heroViz');
  if (!document.documentElement.classList.contains('motion-ok')) return;  // keep static SVG
  var gl = null;
  try { gl = canvas.getContext('webgl', {alpha:true, antialias:true, premultipliedAlpha:false})
             || canvas.getContext('experimental-webgl', {alpha:true, premultipliedAlpha:false}); } catch(e){}
  if (!gl) return;  // no WebGL -> static SVG stays

  // Unified point shader: formation (start->target eased), drift (dust), breathing
  // (nodes), perspective size, depth brightness. Fragment = hot core + soft halo.
  var VERT =
    'attribute vec3 a_target;attribute vec3 a_start;attribute float a_seed;' +
    'uniform mat4 u_mvp;uniform float u_size,u_form,u_time,u_drift,u_breathe;varying float v_b;' +
    'void main(){' +
    'float p=clamp((u_form - a_seed*0.45)/0.55,0.0,1.0);p=1.0-pow(1.0-p,3.0);' +
    'vec3 pos=mix(a_start,a_target,p);' +
    'pos+=u_drift*vec3(sin(u_time*0.3+a_seed*6.283),cos(u_time*0.24+a_seed*9.4),sin(u_time*0.21+a_seed*4.1));' +
    'vec4 mp=u_mvp*vec4(pos,1.0);gl_Position=mp;float z=mp.z/mp.w;' +
    'float br=1.0+u_breathe*sin(u_time*1.7+a_seed*38.0);' +
    'v_b=clamp(0.85-0.5*z,0.28,1.4)*br;gl_PointSize=(u_size*br)/max(mp.w,0.1);}';
  var FRAG =
    'precision mediump float;uniform vec3 u_color;uniform float u_int;varying float v_b;' +
    'void main(){vec2 d=gl_PointCoord-vec2(0.5);float r=length(d)*2.0;float e=clamp(1.0-r,0.0,1.0);' +
    'float core=pow(e,6.0);float halo=pow(e,1.6)*0.42;' +
    'gl_FragColor=vec4(u_color*u_int*v_b, core+halo);}';

  function sh(type, src){ var s=gl.createShader(type); gl.shaderSource(s,src); gl.compileShader(s);
    if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) return null; return s; }
  function restore(){ try{ canvas.hidden=true; }catch(e){} if(fallback) fallback.style.display=''; }
  var vs=sh(gl.VERTEX_SHADER,VERT), fs=sh(gl.FRAGMENT_SHADER,FRAG);
  if(!vs||!fs){ restore(); return; }
  var prog=gl.createProgram(); gl.attachShader(prog,vs); gl.attachShader(prog,fs); gl.linkProgram(prog);
  if(!gl.getProgramParameter(prog,gl.LINK_STATUS)){ restore(); return; }
  gl.useProgram(prog);
  var A_t=gl.getAttribLocation(prog,'a_target'), A_s=gl.getAttribLocation(prog,'a_start'), A_se=gl.getAttribLocation(prog,'a_seed');
  var U_mvp=gl.getUniformLocation(prog,'u_mvp'), U_size=gl.getUniformLocation(prog,'u_size'),
      U_color=gl.getUniformLocation(prog,'u_color'), U_int=gl.getUniformLocation(prog,'u_int'),
      U_form=gl.getUniformLocation(prog,'u_form'), U_time=gl.getUniformLocation(prog,'u_time'),
      U_drift=gl.getUniformLocation(prog,'u_drift'), U_breathe=gl.getUniformLocation(prog,'u_breathe');

  canvas.hidden=false; if(fallback) fallback.style.display='none';   // swap SVG for the live canvas

  // ---- palette (0-1 rgb; cool cyan->violet ramp + warm ember accent) ----
  var C_RING=[0.40,0.72,1.0], C_NODE=[0.58,0.84,1.0], C_COOL=[0.20,0.55,0.62],
      C_VIO=[0.62,0.55,1.0], C_TAIL=[0.78,0.94,1.0], C_EMBER=[0.96,0.62,0.36], C_HOT=[1.0,0.95,0.88];

  var seed=987654321; function rnd(){ seed=(seed*1103515245+12345)&0x7fffffff; return seed/0x7fffffff; }
  var R=1.5, NODES=6, RINGPTS=72;
  var isMobile = Math.min(window.innerWidth, window.innerHeight) < 680 || /Mobi|Android/i.test(navigator.userAgent||'');
  var DUST = isMobile ? 170 : 360;
  function ringPos(t){ var a=t*Math.PI*2; return [Math.cos(a)*R, 0, Math.sin(a)*R]; }
  function scatter(sp){ return [(rnd()*2-1)*sp, (rnd()*2-1)*sp*0.8, (rnd()*2-1)*sp*0.8 - 1.0]; }

  // interleaved [target(3), start(3), seed(1)] stride 28 bytes
  function mkbuf(T,S,Se){ var n=Se.length, arr=new Float32Array(n*7), i, o;
    for(i=0;i<n;i++){ o=i*7; arr[o]=T[i*3];arr[o+1]=T[i*3+1];arr[o+2]=T[i*3+2];
      arr[o+3]=S[i*3];arr[o+4]=S[i*3+1];arr[o+5]=S[i*3+2]; arr[o+6]=Se[i]; }
    var b=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,b); gl.bufferData(gl.ARRAY_BUFFER,arr,gl.STATIC_DRAW);
    return {b:b, n:n}; }

  var i, ringT=[],ringS=[],ringSe=[], nodeT=[],nodeS=[],nodeSe=[];
  for(i=0;i<RINGPTS;i++){ var p=ringPos(i/RINGPTS); ringT.push(p[0],p[1],p[2]); var s=scatter(5.5); ringS.push(s[0],s[1],s[2]); ringSe.push(rnd()); }
  for(i=0;i<NODES;i++){ var q=ringPos(i/NODES); nodeT.push(q[0],q[1],q[2]); var s2=scatter(5.5); nodeS.push(s2[0],s2[1],s2[2]); nodeSe.push(rnd()); }
  // dust partitioned by colour class: ~4% ember, ~20% violet, rest cool
  var coT=[],coS=[],coSe=[], viT=[],viS=[],viSe=[], emT=[],emS=[],emSe=[];
  for(i=0;i<DUST;i++){ var tx=(rnd()*2-1)*3.6, ty=(rnd()*2-1)*2.5, tz=(rnd()*2-1)*2.3-0.5; var st=scatter(6.5); var se=rnd(); var cl=rnd();
    if(cl<0.04){ emT.push(tx,ty,tz); emS.push(st[0],st[1],st[2]); emSe.push(se); }
    else if(cl<0.24){ viT.push(tx,ty,tz); viS.push(st[0],st[1],st[2]); viSe.push(se); }
    else { coT.push(tx,ty,tz); coS.push(st[0],st[1],st[2]); coSe.push(se); } }
  var ringBuf=mkbuf(ringT,ringS,ringSe), nodeBuf=mkbuf(nodeT,nodeS,nodeSe),
      coolBuf=mkbuf(coT,coS,coSe), vioBuf=mkbuf(viT,viS,viSe), emberBuf=mkbuf(emT,emS,emSe);
  var cometBuf=gl.createBuffer();

  // ---- mat4 helpers (column-major) ----
  function mul(a,b){ var o=new Float32Array(16),c,r,k,s;
    for(c=0;c<4;c++)for(r=0;r<4;r++){ s=0; for(k=0;k<4;k++)s+=a[k*4+r]*b[c*4+k]; o[c*4+r]=s; } return o; }
  function persp(fovy,asp,n,f){ var t=1/Math.tan(fovy/2),nf=1/(n-f);
    return new Float32Array([t/asp,0,0,0, 0,t,0,0, 0,0,(f+n)*nf,-1, 0,0,2*f*n*nf,0]); }
  function trans(x,y,z){ return new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, x,y,z,1]); }
  function rotX(a){ var c=Math.cos(a),s=Math.sin(a); return new Float32Array([1,0,0,0, 0,c,s,0, 0,-s,c,0, 0,0,0,1]); }
  function rotY(a){ var c=Math.cos(a),s=Math.sin(a); return new Float32Array([c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1]); }

  var DPR=Math.min(window.devicePixelRatio||1, 2), aspect=1;
  function resize(){ var w=canvas.clientWidth||420, h=canvas.clientHeight||360;
    canvas.width=Math.round(w*DPR); canvas.height=Math.round(h*DPR);
    gl.viewport(0,0,canvas.width,canvas.height); aspect=w/h; }
  resize(); window.addEventListener('resize', resize);

  function bind(o){ gl.bindBuffer(gl.ARRAY_BUFFER,o.b||o);
    gl.enableVertexAttribArray(A_t); gl.vertexAttribPointer(A_t,3,gl.FLOAT,false,28,0);
    gl.enableVertexAttribArray(A_s); gl.vertexAttribPointer(A_s,3,gl.FLOAT,false,28,12);
    gl.enableVertexAttribArray(A_se);gl.vertexAttribPointer(A_se,1,gl.FLOAT,false,28,24); }
  function draw(o, size, col, inten, mvp, form, time, drift, breathe, first, cnt){
    bind(o); gl.uniformMatrix4fv(U_mvp,false,mvp); gl.uniform1f(U_size,size*DPR);
    gl.uniform3fv(U_color,col); gl.uniform1f(U_int,inten); gl.uniform1f(U_form,form);
    gl.uniform1f(U_time,time); gl.uniform1f(U_drift,drift||0); gl.uniform1f(U_breathe,breathe||0);
    gl.drawArrays(gl.POINTS, first||0, cnt!==undefined?cnt:o.n); }

  gl.disable(gl.DEPTH_TEST); gl.enable(gl.BLEND);
  gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE, gl.ONE, gl.ONE);   // additive glow
  gl.clearColor(0,0,0,0);

  // cursor parallax (lerp toward target; research value k=0.07)
  var mtx=0,mty=0, mcx=0,mcy=0;
  window.addEventListener('mousemove', function(e){
    mtx=(e.clientX/window.innerWidth*2-1); mty=(e.clientY/window.innerHeight*2-1); }, {passive:true});

  var TAIL=14;
  var running=false, raf=0, t0=0;
  function render(ms){
    if(!t0) t0=ms; var t=(ms-t0)/1000;
    var form=Math.min(t/1.9, 1.0);                          // formation over 1.9s
    mcx+=(mtx-mcx)*0.07; mcy+=(mty-mcy)*0.07;                // lerp cursor
    var cx=Math.max(-1,Math.min(1,mcx)), cy=Math.max(-1,Math.min(1,mcy));
    var spin=t*0.26;                                        // ~24s / revolution
    var tilt=-1.0 + Math.sin(t*0.3)*0.05;
    var pv=persp(0.92, aspect, 0.1, 100);
    var scene=mul(pv, mul(trans(0,0,-4.7), mul(rotX(tilt + cy*0.16), rotY(spin + cx*0.16))));
    gl.clear(gl.COLOR_BUFFER_BIT);
    // ambient dust (drifting) — cool, violet, ember
    draw(coolBuf, 24, C_COOL, 0.5,  scene, form, t, 0.14, 0.0);
    draw(vioBuf,  26, C_VIO,  0.55, scene, form, t, 0.14, 0.0);
    draw(emberBuf,28, C_EMBER,0.6,  scene, form, t, 0.14, 0.0);
    // the loop ring + breathing nodes
    draw(ringBuf, 40, C_RING, 0.8,  scene, form, t, 0.0, 0.0);
    draw(nodeBuf, 200, C_NODE, 1.75, scene, form, t, 0.0, 0.14);
    // comet: cool fading tail + warm ember head with hot-white core (built each frame)
    var tp=(t*0.11)%1, carr=new Float32Array(TAIL*7), k, o, cp;
    for(k=0;k<TAIL;k++){ cp=ringPos(tp - k*0.011); o=k*7;
      carr[o]=cp[0];carr[o+1]=cp[1];carr[o+2]=cp[2]; carr[o+3]=cp[0];carr[o+4]=cp[1];carr[o+5]=cp[2]; carr[o+6]=0; }
    gl.bindBuffer(gl.ARRAY_BUFFER,cometBuf); gl.bufferData(gl.ARRAY_BUFFER,carr,gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(A_t); gl.vertexAttribPointer(A_t,3,gl.FLOAT,false,28,0);
    gl.enableVertexAttribArray(A_s); gl.vertexAttribPointer(A_s,3,gl.FLOAT,false,28,12);
    gl.enableVertexAttribArray(A_se);gl.vertexAttribPointer(A_se,1,gl.FLOAT,false,28,24);
    gl.uniformMatrix4fv(U_mvp,false,scene); gl.uniform1f(U_form,1.0); gl.uniform1f(U_time,t);
    gl.uniform1f(U_drift,0); gl.uniform1f(U_breathe,0);
    for(k=TAIL-1;k>=1;k--){ var f=k/TAIL;                   // tail fades out
      gl.uniform3fv(U_color,C_TAIL); gl.uniform1f(U_size,(28+(1.0-f)*70)*DPR); gl.uniform1f(U_int,(1.0-f)*1.0+0.12);
      gl.drawArrays(gl.POINTS,k,1); }
    var hb=(0.9 + 0.15*Math.sin(t*2.2)) * form;             // head breathes + fades in with formation
    gl.uniform3fv(U_color,C_EMBER); gl.uniform1f(U_size,240*DPR*hb); gl.uniform1f(U_int,2.2*hb); gl.drawArrays(gl.POINTS,0,1);
    gl.uniform3fv(U_color,C_HOT);   gl.uniform1f(U_size,105*DPR*hb); gl.uniform1f(U_int,2.7*hb); gl.drawArrays(gl.POINTS,0,1);
    if(running) raf=requestAnimationFrame(render);
  }
  function start(){ if(running) return; running=true; raf=requestAnimationFrame(render); }
  function stop(){ running=false; if(raf) cancelAnimationFrame(raf); raf=0; }

  document.addEventListener('visibilitychange', function(){ if(document.hidden) stop(); else if(onscreen) start(); });
  var onscreen=true;
  if('IntersectionObserver' in window){
    new IntersectionObserver(function(es){ es.forEach(function(e){
      onscreen=e.isIntersecting && e.intersectionRatio>0.08;
      if(onscreen && !document.hidden) start(); else stop();
    }); }, {threshold:[0,0.08,0.5]}).observe(viz);
  } else { start(); }
  start();
})();
