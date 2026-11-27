/*!
 * Liquid Glass - vanilla JavaScript port of liquid-glass-react
 *   https://github.com/rdev/liquid-glass-react
 *   Copyright 2025 Max Rovensky - MIT License (see THIRD_PARTY_LICENSES.md)
 *   Itself adapted from https://github.com/shuding/liquid-glass
 *
 * Same technique as the original React component:
 *   1. a backdrop layer (blur + saturate) bent by an SVG feDisplacementMap,
 *      with per-channel offsets for chromatic aberration at the edges;
 *   2. two masked specular rings whose light angle follows the pointer;
 *   3. optional elastic stretch towards the pointer and hover/press highlights.
 * Refraction needs a Chromium engine (WebView2, Chrome, Edge); elsewhere it
 * falls back to the plain frosted blur, exactly like the original.
 *
 * Usage:  LiquidGlass.attach(element, { refract: true, mode: "shader", ... })
 */
"use strict";
(() => {
  const STANDARD_MAP = "data:image/jpeg;base64,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cUAUAkEkziomgGgkoxZGgxZFQFQlYnQHRdPfj/10KCSCKESCNiVkViPSLpD0h6I0Q0I0A2IoBWBIJIBKBIJoJIJ2R2J0JWBUJ0JUB0XTv479dFZDYiglYigkhEgjZFQjRFQjRFQjQigFYigHYigmgEgmglYlYnQlQlYlQHQlQnQ9P/kf1yVkNiNCNkNiVENiNiViNEViNkVCVgKCViViViSCViSCVgdCViVCViVCdgVCVCdD1D+U/XBWQ2I0I2Q2JUQ2I0JWQ0I2JUQ2JUI2JUI2J0JWJWJWA2R0BWJ0I2JUJ2BUJUJ0P//EABkQAQEBAQEBAAAAAAAAAAAAAAECABEDEP/aAAgBAQABAgB1atWrVq1atWrVq1atWrVq1atWrVq1atWrVq+OrVq1atWrVq1atWrVq1atWrVq1atWrVq1atXxVppppppdWrVq1atWrVq1NNNNNNNNNNNPVWmmmmms6tWrVq1atWpppppppppppppp6q0000uc51atWrVq1ammmmmmmmmmmmmt1Vpppc5znVq1atWrVqaaaaaaaaaaaaaeqtNLnOc51atWrVq1ammmmmmmmmmmmmnqrS5znOc6tWrVq16222mmmmmmlVppp6tKuc5znOrVq1a9TbbbbTTTTTSq000qtLnOc5zq1atWrW0222200000qqqtKqrnOc5zq1atTbbbbbbbbTTTSqqqqqq5znOc6tTTTbbbbbbbbTTTSqqqqrlVznOctNNNtttttttttNNNNKqqqrqznKqrTTTTbbbbbbbbbTTTSqqqqrqznOc5aaaabbbbbbbbbaaaaVVVVVdWc5znVq1NNttttttttttNNKqqqqudWc5znVq16tbbbbbbbbbbTTSqqqq5XVnOc6tWrVrb1tttttttttNNKqqqqrWrK5VWmmm2230bbbbbbaaaXOc5zlVa1KuVVppptttt9G22222mmlzlVznK6tWVVWmmmm2222222222mlznOc5znLWppVVWmmm22222229bTWrOc5znOcq1qaaVpWmm222222229erVqznOc5znKtatStK0rTbTTbbbberXr1as5znOc5aVpppppWlabaabbbb1ta9WrVnOc5znU0rTTTTTTTTTbTTbbbTWvVq1as5znOdTTStNNNNNNNNNtNNtttN6tWvVq1ZznOrU00rTTTTTTTTTTTTTbTWvVq1atWrOc6tTTTStNNNNNNNNNNtNNtNa9WrVq1Z1Z1NNNNNK1q1NNNNNNNNNNNtNatWrVq1atWrU00000rWrVq1atWrVq1alaaa1atWrVq1NNNammmmla1atWrVq1aterVq16tWrVnVqa1NK1qaaaVX/xAAWEAADAAAAAAAAAAAAAAAAAAAhgJD/2gAIAQEAAz8AaExf/8QAGhEBAQEBAQEBAAAAAAAAAAAAAQISEQADEP/aAAgBAgEBAgDx48ePHjx48ePHjx48ePHjx48ePHjx48ePHj86IiIiIiInjx48ePHjx48IiIiIj0oooooooooRERER73ve60UUUUUUVrWiiiiiihERERER73ve97ooooorRWiiiiihKERERER73ve973RRRRWtFFFFFFCIiIiIiPe973ve60UUVrRRRRRRQiIlCIiI973ve973pRRWiiiiiiiiiiiiiiihEe973ve973RRWtFFFFFFFFFFFFFFFFFFa13ve973WitaKKKKKKKKKKKKKKKKKK1rWtd1rutFa1oooooooooooosssooorWta1rWta1rRRRRRRRRRRZZZZZZZZZWta1rWta1rRRRRRRRRZZZZZZZZZZZZe9a1rWta1rWitaKLLLLLLLLLLLLLLLLL3rWta1rWtFbLLLLLLLLLLLLLLLLLLLL3vWta1rWita1ssssssss+hZZZZZZZZe961rWta0Vre97LLLLLLLLLLLPoWWWWWXrWta1oorWta3ssss+hZZZZ9Cyyyyyyyyiita1orWta1ve9llllllllllllllllFFa0VorWta1ve9llllllllllllllllllFFFaK1rWta1rWiyyyyyyyyyyyyiiiiiiitFFa1rWta1oosoosssssoooosoooorRRRWta1rWta0UUUUUWUUUUUUUUUUUVoooorWta1rWtaKKKKKKmiiiiiiiiiiiiiiitd73ve61oSiiipoqaKKKKKKKKKK0UUUVrve973vREREZoSihEooooorRRRRWtd73ve9EREREREoSiiiiitFllllla73ve9ERERERESiiiiiitH0PoWWWWVrXe96IiIiMoiJRRRRRRWjwlFFllllFFd6IiIiIlCUUUUUUUUUePHjx48ePCIiIiIiIiUUUUUUUUUUUePHjx48ePHjx48ePHjx48IiUUUUUUJRRRX//xAAWEQADAAAAAAAAAAAAAAAAAAABYJD/2gAIAQIBAz8AtEV7/8QAFxEBAQEBAAAAAAAAAAAAAAAAAAECEP/aAAgBAwEBAgCtNNNNNNNNNNNNNNNNNNNNNNNNNNNNNcrTTTTTTTTTTTTTTTTTTTTTTTTTTTTTXKrTTTTTTTU000000000000000000001FVpppppqampqaaaaaaaaaaaaaaaaaaaa5Vaaaaampqampqammmmmmmmmmmlaaaaaaiq0001NTU1NTU1NTTTTTTTTTTSqqtNNNcqtNNSyzU1LNTU1NTTTTTTTTTSqqq001ytNLLLLNTU1NTU1NTbbbTTTTTSqqq001ytNLLLLLNTU1NTU3NttttNNNNNKqq001KrSyyyyyzU1NTU3Nzc02220000qqqqrSqqyyyyyzU1NTU3Nzc3NttttNNNKqqqqqqssssss1NTU3Nzc3NzbbbbTTTSqqqqqqrLLLLLNTU1Nzc3Nzc22220000qqqqqqqqssss1NTU3Nzc3NzbbbbbTTSqqqqqqqqqqzU1NTc3Nzc3Nzbc22000qqqqqqqqqqqtTU3Nzc3Nzc3NtzbTTSqqqqrKqqqqqtNNzc23Nzc3Nzc3NTU1KqqqrKqqqqqtNNNNttzc3Nzc3NzU1NLLLLLKqqqqqqqq0022223Nzc3NzU1NSyyyyyyqqqqqqqrTTbbbbc3Nzc3NTU1LLLLLLKsqqqqqqrTTTTbbbc3Nzc1NTUsssssssqqqqqqrTTTTTbbbTc3NTU1NTUsssssqqqqqqqq0000222023NTU1NTUsssssqqqqqqqq000000003NTU1NTU1LLLLLNKrTSqqqqtNNNNNNtNNTU1NSzUssss00qq0qqqqrTTTTTTTTTU1NTUs1LLLNNNKrTTTSqqq00000000001NTU1LNTU0000qtNNNKqqqtNNNNNNNNTU1NTUs1NNNNNKss1NNNK00qtK0000001NNTU0s000000qq000001NKrStNNNNK1NNNNStNNNNNKqtNNNNNNNK0000000rU0000rTTTTTSq00000rTTTTTTTTTTTTTTTTStNNNNKr/xAAUEQEAAAAAAAAAAAAAAAAAAACg/9oACAEDAQM/AAAf/9k=";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const DEFAULTS = {
    refract: false,        // bend the backdrop (only for surfaces floating over the map)
    mode: "standard",      // "standard" (pre-baked map) | "shader" (generated per element size)
    displacement: 70,      // displacementScale
    blur: 0.0625,          // blurAmount -> blur(4 + blur * 32 px)
    blurPx: null,          // exact blur in px (overrides `blur`); Apple's "clear" glass is ~2-3 px
    saturation: 140,       // %
    brightness: 1,         // backdrop brightness; Apple's light glass lifts what is behind it
    aberration: 2,         // chromatic aberration intensity
    elasticity: 0,         // 0 = static; 0.15 = original default for buttons
    interactive: false,    // hover / press highlights + press scale
  };

  const canRefract = !/firefox/i.test(navigator.userAgent) &&
    CSS.supports("backdrop-filter", "blur(1px)") &&
    !matchMedia("(prefers-reduced-transparency: reduce)").matches;
  let uid = 0;

  // ---------- shader displacement map (port of shader-utils.ts) ----------
  const smoothStep = (a, b, t) => { t = Math.max(0, Math.min(1, (t - a) / (b - a))); return t * t * (3 - 2 * t); };
  function roundedRectSDF(x, y, w, h, r) {
    const qx = Math.abs(x) - w + r, qy = Math.abs(y) - h + r;
    return Math.min(Math.max(qx, qy), 0) + Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) - r;
  }
  function liquidGlassFragment(u, v) {
    const ix = u - 0.5, iy = v - 0.5;
    const scaled = smoothStep(0, 1, smoothStep(0.8, 0, roundedRectSDF(ix, iy, 0.3, 0.2, 0.6) - 0.15));
    return [ix * scaled + 0.5, iy * scaled + 0.5];
  }
  const shaderCache = new Map();
  function shaderMap(width, height) {
    const w = Math.max(2, Math.round(width)), h = Math.max(2, Math.round(height)), key = w + "x" + h;
    if (shaderCache.has(key)) return shaderCache.get(key);
    const raw = new Float32Array(w * h * 2);
    let max = 0;
    for (let y = 0, i = 0; y < h; y++) {
      for (let x = 0; x < w; x++, i += 2) {
        const [px, py] = liquidGlassFragment(x / w, y / h);
        const dx = px * w - x, dy = py * h - y;
        max = Math.max(max, Math.abs(dx), Math.abs(dy));
        raw[i] = dx; raw[i + 1] = dy;
      }
    }
    max = Math.max(max, 1);
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext("2d"), img = ctx.createImageData(w, h), d = img.data;
    for (let y = 0, i = 0, p = 0; y < h; y++) {
      for (let x = 0; x < w; x++, i += 2, p += 4) {
        const edge = Math.min(1, Math.min(x, y, w - x - 1, h - y - 1) / 2);  // soften the outer 2 px
        const r = (raw[i] * edge) / max + 0.5, g = (raw[i + 1] * edge) / max + 0.5;
        d[p] = Math.max(0, Math.min(255, r * 255));
        d[p + 1] = d[p + 2] = Math.max(0, Math.min(255, g * 255));
        d[p + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    const url = canvas.toDataURL();
    if (shaderCache.size > 24) shaderCache.clear();
    shaderCache.set(key, url);
    return url;
  }

  // ---------- SVG filter (port of GlassFilter) ----------
  const el = (tag, attrs = {}, parent) => {
    const n = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };
  const MATRIX = {
    edge: "0.3 0.3 0.3 0 0 0.3 0.3 0.3 0 0 0.3 0.3 0.3 0 0 0 0 0 1 0",
    r: "1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0",
    g: "0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 1 0",
    b: "0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 1 0",
  };
  function buildFilter(id, o) {
    const svg = el("svg", { width: "0", height: "0", "aria-hidden": "true", class: "lg-svg" });
    const f = el("filter", { id, x: "-35%", y: "-35%", width: "170%", height: "170%", "color-interpolation-filters": "sRGB" }, el("defs", {}, svg));
    const image = el("feImage", { x: "0", y: "0", width: "1", height: "1", result: "MAP", preserveAspectRatio: "xMidYMid slice", href: STANDARD_MAP }, f);
    el("feColorMatrix", { in: "MAP", type: "matrix", values: MATRIX.edge, result: "EDGE_INTENSITY" }, f);
    el("feFuncA", { type: "discrete", tableValues: `0 ${o.aberration * 0.05} 1` }, el("feComponentTransfer", { in: "EDGE_INTENSITY", result: "EDGE_MASK" }, f));
    el("feOffset", { in: "SourceGraphic", dx: "0", dy: "0", result: "CENTER" }, f);
    const sign = o.mode === "shader" ? 1 : -1, disp = {};
    [["r", 0], ["g", 0.05], ["b", 0.1]].forEach(([c, k]) => {
      disp[c] = el("feDisplacementMap", { in: "SourceGraphic", in2: "MAP", scale: o.displacement * (sign - o.aberration * k), xChannelSelector: "R", yChannelSelector: "B", result: c + "D" }, f);
      el("feColorMatrix", { in: c + "D", type: "matrix", values: MATRIX[c], result: c + "C" }, f);
    });
    el("feBlend", { in: "gC", in2: "bC", mode: "screen", result: "GB" }, f);
    el("feBlend", { in: "rC", in2: "GB", mode: "screen", result: "RGB" }, f);
    el("feGaussianBlur", { in: "RGB", stdDeviation: Math.max(0.1, 0.5 - o.aberration * 0.1), result: "SOFT" }, f);
    el("feComposite", { in: "SOFT", in2: "EDGE_MASK", operator: "in", result: "EDGE_ABERRATION" }, f);
    el("feFuncA", { type: "table", tableValues: "1 0" }, el("feComponentTransfer", { in: "EDGE_MASK", result: "INVERTED" }, f));
    el("feComposite", { in: "CENTER", in2: "INVERTED", operator: "in", result: "CENTER_CLEAN" }, f);
    el("feComposite", { in: "EDGE_ABERRATION", in2: "CENTER_CLEAN", operator: "over" }, f);
    return { svg, image };
  }

  // ---------- attach ----------
  const span = (cls) => Object.assign(document.createElement("span"), { className: "lg-layer " + cls });

  function attach(node, options = {}) {
    if (!node || node.__lg) return node;
    const o = { ...DEFAULTS, ...options };
    const refract = o.refract && canRefract && !LiquidGlass.disabled;
    const layers = [];
    node.__lg = o;
    node.classList.add("lg");
    if (getComputedStyle(node).position === "static") node.style.position = "relative";

    if (refract) {
      const id = "lg-filter-" + (++uid);
      const { svg, image } = buildFilter(id, o);
      const warp = span("lg-warp");
      warp.style.filter = `url(#${id})`;
      const blurPx = o.blurPx ?? 4 + o.blur * 32;
      warp.style.backdropFilter = warp.style.webkitBackdropFilter =
        `blur(${blurPx}px) saturate(${o.saturation}%) brightness(${o.brightness})`;
      // The tint must NOT be painted by the warp itself: the displacement filter would split
      // a semi-transparent tint into R/G/B and blend it back as gray (the original has no tint).
      layers.push(svg, warp, span("lg-tint"));
      node.classList.add("lg-refract");
      let timer;
      const resize = () => {
        const w = node.offsetWidth, h = node.offsetHeight;
        if (!w || !h) return;
        image.setAttribute("width", w);
        image.setAttribute("height", h);
        if (o.mode === "shader") {   // regenerating is costly: wait until resizing settles
          clearTimeout(timer);
          timer = setTimeout(() => image.setAttribute("href", shaderMap(node.offsetWidth, node.offsetHeight)), 120);
        }
      };
      new ResizeObserver(resize).observe(node);
      resize();
    }
    layers.push(span("lg-edge lg-edge-1"), span("lg-edge lg-edge-2"));
    if (o.interactive) layers.push(span("lg-hover lg-hover-1"), span("lg-hover lg-hover-2"), span("lg-hover lg-hover-3"));
    node.prepend(...layers);
    if (o.elasticity > 0) node.classList.add("lg-elastic");
    if (o.interactive) node.classList.add("lg-interactive");

    // Pointer-driven specular angle + elastic stretch (formulas from the original).
    let frame = 0, last = null;
    const update = () => {
      frame = 0;
      if (!last) return;
      const r = node.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const dx = last.x - cx, dy = last.y - cy;
      const mx = (dx / r.width) * 100, my = (dy / r.height) * 100, k = Math.abs(mx);
      const s = node.style;
      s.setProperty("--lg-ang", 135 + mx * 1.2 + "deg");
      s.setProperty("--lg-p1", Math.max(10, 33 + my * 0.3) + "%");
      s.setProperty("--lg-p2", Math.min(90, 66 + my * 0.4) + "%");
      s.setProperty("--lg-a1", 0.12 + k * 0.008); s.setProperty("--lg-a2", 0.4 + k * 0.012);
      s.setProperty("--lg-b1", 0.32 + k * 0.008); s.setProperty("--lg-b2", 0.6 + k * 0.012);
      // Pointer position inside the element: Apple's glass lights up where it is touched.
      s.setProperty("--lg-x", ((last.x - r.left) / r.width) * 100 + "%");
      s.setProperty("--lg-y", ((last.y - r.top) / r.height) * 100 + "%");
      if (o.elasticity > 0) {
        const dist = Math.hypot(dx, dy);
        s.translate = `${dx * o.elasticity * 0.1}px ${dy * o.elasticity * 0.1}px`;
        if (dist > 0) {
          const st = Math.min(dist / 300, 1) * o.elasticity, nx = Math.abs(dx / dist), ny = Math.abs(dy / dist);
          s.scale = `${Math.max(0.8, 1 + nx * st * 0.3 - ny * st * 0.15)} ${Math.max(0.8, 1 + ny * st * 0.3 - nx * st * 0.15)}`;
        }
      }
    };
    node.addEventListener("pointermove", e => { last = { x: e.clientX, y: e.clientY }; if (!frame) frame = requestAnimationFrame(update); });
    node.addEventListener("pointerenter", () => node.classList.add("lg-hovered"));
    node.addEventListener("pointerleave", () => {
      last = null;
      node.classList.remove("lg-hovered", "lg-active");
      ["--lg-ang", "--lg-p1", "--lg-p2", "--lg-a1", "--lg-a2", "--lg-b1", "--lg-b2", "--lg-x", "--lg-y", "translate", "scale"].forEach(p => node.style.removeProperty(p));
    });
    if (o.interactive) {
      node.addEventListener("pointerdown", e => {
        last = { x: e.clientX, y: e.clientY }; update();   // glow starts exactly under the finger
        node.classList.add("lg-active");
      });
      ["pointerup", "pointercancel"].forEach(ev => node.addEventListener(ev, () => node.classList.remove("lg-active")));
    }
    return node;
  }

  const attachAll = (selector, options, root = document) => root.querySelectorAll(selector).forEach(n => attach(n, options));

  // Change an element's label without removing the glass layers inside it.
  function setText(node, text) {
    if (!node.__lg) { node.textContent = text; return; }
    let t = [...node.childNodes].find(c => c.nodeType === Node.TEXT_NODE && c.data.trim());
    if (!t) t = node.appendChild(document.createTextNode(""));
    t.data = text;
  }

  window.LiquidGlass = { attach, attachAll, setText, canRefract, disabled: false };
})();
