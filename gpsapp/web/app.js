"use strict";
(() => {
  const CFG = window.APP_CONFIG;
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const store = {
    get: (k, d = null) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage disabled */ } },
  };

  // ---------- i18n ----------
  let lang = store.get("lang") || ((navigator.language || "es").toLowerCase().startsWith("es") ? "es" : "en");
  if (!window.I18N[lang]) lang = "en";
  const t = (key, vars = {}) => {
    const s = window.I18N[lang][key] ?? window.I18N.en[key] ?? key;
    return typeof s === "string" ? s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "") : s;
  };
  const LG = window.LiquidGlass;
  const setText = LG.setText;   // keeps the glass layers inside buttons intact
  function applyI18n() {
    document.documentElement.lang = lang;
    $$("[data-i18n]").forEach(el => setText(el, t(el.dataset.i18n)));
    $$("[data-i18n-html]").forEach(el => { el.innerHTML = t(el.dataset.i18nHtml); });  // trusted, static strings
    $$("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
    $$("[data-i18n-aria]").forEach(el => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
    $$("[data-i18n-title]").forEach(el => { el.title = t(el.dataset.i18nTitle); });
    $("#version").textContent = t("version", { v: CFG.version });
    $("#menu-pill").setAttribute("aria-label", t("show_menu"));
    updatePillWidth();
    renderDynamic();
  }

  // ---------- API ----------
  async function api(path, body, method) {
    const opts = { method: method || (body === undefined ? "GET" : "POST"), headers: { "X-Token": CFG.token } };
    if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    const r = await fetch("/api/" + path, opts);
    return r.json();
  }
  const quiet = p => p.catch(() => null);

  // ---------- helpers ----------
  const toast = msg => {
    const el = $("#toast");
    window.LiquidGlass.setText(el, msg); el.classList.add("show");
    clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove("show"), 3500);
  };
  const R = 6371000, rad = d => d * Math.PI / 180;
  function distM(a, b) {
    const x = Math.sin(rad(b.lat - a.lat) / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lon - a.lon) / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(x)));
  }
  const pathLength = pts => pts.reduce((s, p, i) => i ? s + distM(pts[i - 1], p) : 0, 0);
  const fmtDist = m => m >= 1000 ? `${(m / 1000).toFixed(m >= 10000 ? 1 : 2)} km` : `${Math.round(m)} m`;
  const fmtTime = s => s >= 3600 ? `${Math.floor(s / 3600)} h ${Math.round(s % 3600 / 60)} min` : s >= 60 ? `${Math.round(s / 60)} min` : `${Math.round(s)} s`;
  const fmtCoords = (a, b) => `${a.toFixed(6)}, ${b.toFixed(6)}`;
  function offsetM(lat, lon, north, east) {
    return [lat + north / 111320, lon + east / (111320 * Math.max(0.01, Math.cos(rad(lat))))];
  }

  // ---------- presets ----------
  const MODES = {
    walk: { speed: 5, step: 1, color: "#28cd41", osrm: "routed-foot" },
    bike: { speed: 18, step: 2, color: "#ff9f0a", osrm: "routed-bike" },
    car: { speed: 45, step: 3, color: "#007aff", osrm: "routed-car" },
  };
  const STEPS = { 1: 10, 2: 25, 3: 60 };   // meters per key press
  const DIRS = { n: [1, 0], s: [-1, 0], e: [0, 1], w: [0, -1] };
  const KEYS = { w: "n", arrowup: "n", s: "s", arrowdown: "s", a: "w", arrowleft: "w", d: "e", arrowright: "e" };

  // ---------- state ----------
  const S = {
    lat: CFG.start.lat, lon: CFG.start.lon, serverVersion: -1, localMoveAt: 0,
    mode: "car", step: 2, mapLayer: "map",
    adding: false, waypoints: [], path: [], pathKind: "kind_straight", pathSeq: 0, pathPromise: null,
    favorites: [], history: [], last: null,
  };

  // ---------- map ----------
  const tiles = {
    map: L.tileLayer(CFG.tiles.map, { maxZoom: 19, attribution: CFG.tiles.map_attr }),
    sat: L.tileLayer(CFG.tiles.sat, { maxZoom: 19, attribution: CFG.tiles.sat_attr }),
  };
  const map = L.map("map", { layers: [tiles.map], zoomControl: false }).setView([S.lat, S.lon], 15);
  L.control.zoom({ position: "topright" }).addTo(map);
  const marker = L.marker([S.lat, S.lon], { draggable: true, keyboard: false }).addTo(map);
  const wpLayer = L.layerGroup().addTo(map);
  let routeLine = null;

  function setLayer(name) {
    S.mapLayer = name;
    Object.entries(tiles).forEach(([k, layer]) => k === name ? map.addLayer(layer) : map.removeLayer(layer));
  }

  function showPosition(pan) {
    marker.setLatLng([S.lat, S.lon]);
    $("#coords").textContent = fmtCoords(S.lat, S.lon);
    if (pan || $("#follow-marker").checked) map.panTo([S.lat, S.lon], { animate: true, duration: 0.3 });
  }

  function moveTo(lat, lon, { zoom = false } = {}) {
    S.lat = +lat; S.lon = +lon; S.localMoveAt = Date.now();
    if (zoom) map.setView([S.lat, S.lon], Math.max(map.getZoom(), 16));
    showPosition(false);
    quiet(api("move", { lat: S.lat, lon: S.lon }));
    if ($("#hist-sec").open) setTimeout(loadHistory, 300);
  }

  function nudge(dir) {
    const [n, e] = DIRS[dir];
    const [lat, lon] = offsetM(S.lat, S.lon, n * STEPS[S.step], e * STEPS[S.step]);
    moveTo(lat, lon);
  }

  map.on("click", e => {
    if (S.adding) {
      S.waypoints.push({ lat: e.latlng.lat, lon: e.latlng.lng });
      redrawRoute();
    } else {
      moveTo(e.latlng.lat, e.latlng.lng);
    }
  });
  marker.on("dragend", e => { const p = e.target.getLatLng(); moveTo(p.lat, p.lng); });

  // ---------- segmented controls ----------
  function placeThumb(seg) {
    const active = $(".seg-opt.active", seg), thumb = $(".thumb", seg);
    if (!active || !thumb || !active.offsetWidth) return;
    const first = !thumb.style.width;
    if (first) thumb.style.transition = "none";
    thumb.style.width = active.offsetWidth + "px";
    thumb.style.transform = `translateX(${active.offsetLeft}px)`;
    if (first) { void thumb.offsetWidth; thumb.style.transition = ""; }
  }
  const segHandlers = {};
  function setSeg(group, value) {
    const seg = $(`.segmented[data-group="${group}"]`);
    $$(".seg-opt", seg).forEach(b => b.classList.toggle("active", b.dataset.value === String(value)));
    placeThumb(seg);
  }
  $$(".segmented").forEach(seg => {
    const thumb = document.createElement("span");
    thumb.className = "thumb";
    seg.prepend(thumb);
    new ResizeObserver(() => placeThumb(seg)).observe(seg);
    seg.addEventListener("click", e => {
      const btn = e.target.closest(".seg-opt");
      if (!btn) return;
      setSeg(seg.dataset.group, btn.dataset.value);
      segHandlers[seg.dataset.group]?.(btn.dataset.value);
    });
  });

  segHandlers.layer = setLayer;
  segHandlers.step = v => setStep(+v);
  segHandlers.mode = v => setMode(v);
  segHandlers.lang = v => { lang = v; store.set("lang", v); applyI18n(); };

  function setStep(level) {
    S.step = level;
    setSeg("step", level);
    $("#step-info").textContent = t("step_info", { m: STEPS[level] });
    quiet(api("step", { meters: STEPS[level] }));   // used by the global hotkeys
  }

  function setMode(mode) {
    S.mode = mode;
    setSeg("mode", mode);
    setStep(MODES[mode].step);
    setSlider($("#route-speed"), MODES[mode].speed);
    redrawRoute();
  }

  // ---------- sliders & switches ----------
  function syncSlider(el) {
    el.style.setProperty("--p", ((el.value - el.min) / (el.max - el.min) * 100) + "%");
    if (el.id === "route-speed") $("#speed-val").textContent = `${el.value} km/h`;
    if (el.id === "route-dwell") $("#dwell-val").textContent = `${el.value} s`;
  }
  function setSlider(el, v) { el.value = v; syncSlider(el); el.dispatchEvent(new Event("input")); }
  $$("input[type=range]").forEach(el => {
    el.addEventListener("input", () => syncSlider(el));
    el.addEventListener("pointerup", () => el.blur());  // keep WASD working after dragging
    syncSlider(el);
  });
  $$(".switch input").forEach(i => i.addEventListener("click", e => { if (e.detail) i.blur(); }));

  let speedTimer;
  $("#route-speed").addEventListener("input", () => {
    updateRouteStats();
    clearTimeout(speedTimer);
    speedTimer = setTimeout(() => quiet(api("route/config", { speed_kmh: +$("#route-speed").value })), 150);
  });
  $("#route-jitter").addEventListener("change", e => quiet(api("route/config", { jitter: e.target.checked })));
  $("#route-loop").addEventListener("change", e => quiet(api("route/config", { loop: e.target.checked })));
  $("#route-streets").addEventListener("change", redrawRoute);

  // ---------- routing ----------
  async function osrmRoute(points, mode) {
    const coords = points.map(p => `${p.lon.toFixed(6)},${p.lat.toFixed(6)}`).join(";");
    const url = `https://routing.openstreetmap.de/${MODES[mode].osrm}/route/v1/driving/${coords}?overview=full&geometries=geojson`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error("routing " + resp.status);
    const data = await resp.json();
    const coordsOut = data.routes?.[0]?.geometry?.coordinates;
    if (!coordsOut || coordsOut.length < 2) throw new Error("no route");
    return coordsOut.map(c => ({ lat: c[1], lon: c[0] }));
  }

  function buildPath() {
    const seq = ++S.pathSeq, wps = S.waypoints.slice();
    const streets = $("#route-streets").checked && wps.length >= 2 && wps.length <= 100;
    S.pathPromise = (async () => {
      let path = wps, kind = "kind_straight";
      if (streets) {
        try { path = await osrmRoute(wps, S.mode); kind = "kind_streets"; }
        catch { kind = "kind_offline"; }
      }
      if (seq === S.pathSeq) {         // ignore results of outdated requests
        S.path = path; S.pathKind = kind;
        if (routeLine) routeLine.setLatLngs(path.map(p => [p.lat, p.lon]));
        updateRouteStats();
      }
      return path;
    })();
    return S.pathPromise;
  }

  function redrawRoute() {
    wpLayer.clearLayers();
    S.waypoints.forEach((p, i) => L.circleMarker([p.lat, p.lon], { radius: 5, color: "#fff", fillColor: "#007aff", fillOpacity: 1, weight: 2 })
      .bindTooltip(String(i + 1)).addTo(wpLayer));
    if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
    S.path = S.waypoints.slice(); S.pathKind = "kind_straight";
    if (S.waypoints.length >= 2) {
      routeLine = L.polyline(S.path.map(p => [p.lat, p.lon]), { color: MODES[S.mode].color, weight: 4, opacity: .9 }).addTo(map);
      buildPath();
    } else {
      S.pathSeq++; S.pathPromise = null;
    }
    renderRouteInfo();
    updateRouteStats();
  }

  function renderRouteInfo() {
    $("#route-info").textContent = t("route_info", { mode: t("mode_" + S.mode), n: S.waypoints.length });
    const btn = $("#btn-route-add");
    setText(btn, t(S.adding ? "adding" : "add_points"));
    btn.classList.toggle("btn-primary", S.adding);
    map.getContainer().classList.toggle("adding", S.adding);
  }

  function updateRouteStats() {
    const pts = S.path.length >= 2 ? S.path : S.waypoints;
    if (pts.length < 2) { $("#route-stats").textContent = ""; return; }
    const m = pathLength(pts), speed = Math.max(1, +$("#route-speed").value);
    $("#route-stats").textContent = t("route_stats", { dist: fmtDist(m), time: fmtTime(m / (speed / 3.6)), kind: t(S.pathKind) });
  }

  // Path index closest to each waypoint (searching forward), so the engine knows where to dwell.
  function stopIndexes(path) {
    const out = []; let from = 0;
    S.waypoints.slice(1).forEach(w => {
      let best = from, bd = Infinity;
      for (let i = from; i < path.length; i++) { const d = distM(w, path[i]); if (d < bd) { bd = d; best = i; } }
      out.push(best); from = best;
    });
    return out;
  }

  function setAdding(on) { S.adding = on; renderRouteInfo(); }

  $("#btn-route-add").onclick = () => setAdding(!S.adding);
  $("#btn-route-undo").onclick = () => { if (S.waypoints.pop()) redrawRoute(); };
  $("#btn-route-clear").onclick = () => { S.waypoints = []; setAdding(false); redrawRoute(); quiet(api("route/clear", {})); };
  $("#btn-route-run").onclick = async () => {
    if (S.waypoints.length < 2) return toast(t("need_2_points"));
    setAdding(false);
    const path = (await S.pathPromise) || S.path;
    await quiet(api("route/start", {
      points: path, stops: stopIndexes(path),
      speed_kmh: +$("#route-speed").value, dwell: +$("#route-dwell").value,
      loop: $("#route-loop").checked, jitter: $("#route-jitter").checked,
    }));
    poll();
  };
  $("#btn-route-pause").onclick = () => quiet(api("route/pause", {})).then(poll);

  // ---------- GPX ----------
  $("#btn-gpx-export").onclick = async () => {
    const pts = S.path.length >= 2 ? S.path : S.waypoints;
    if (pts.length < 2) return toast(t("need_2_points"));
    const d = await quiet(api("gpx/export", { points: pts }));
    if (d?.ok) toast(t("saved_to", { path: d.path })); else if (!d?.cancelled) toast(t("save_failed"));
  };
  $("#btn-gpx-import").onclick = () => $("#gpx-file").click();
  $("#gpx-file").onchange = async e => {
    const file = e.target.files[0]; e.target.value = "";
    if (!file) return;
    const doc = new DOMParser().parseFromString(await file.text(), "application/xml");
    let pts = $$("trkpt, rtept", doc);
    if (pts.length < 2) pts = $$("wpt", doc);
    pts = pts.map(n => ({ lat: +n.getAttribute("lat"), lon: +n.getAttribute("lon") }))
      .filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lon));
    if (pts.length < 2) return toast(t("gpx_bad"));
    const k = Math.ceil(pts.length / 500);   // keep the UI responsive with huge tracks
    if (k > 1) pts = pts.filter((_, i) => i % k === 0 || i === pts.length - 1);
    $("#route-streets").checked = false;
    S.waypoints = pts; redrawRoute();
    map.fitBounds(pts.map(p => [p.lat, p.lon]), { padding: [40, 40] });
    toast(t("gpx_loaded", { n: pts.length }));
  };

  // ---------- search ----------
  const input = $("#search-input"), box = $("#suggest-list");
  let suggestTimer, suggestSeq = 0, suggestions = [], sel = -1;
  const hideSuggest = () => { box.hidden = true; box.replaceChildren(); suggestions = []; sel = -1; };
  function renderSuggest(items) {
    suggestions = items; sel = -1;
    box.replaceChildren(...items.map((it, i) => {
      const div = document.createElement("div");
      div.className = "suggest-item"; div.textContent = it.label; div.setAttribute("role", "option");
      div.onclick = () => pickSuggestion(i);
      return div;
    }));
    box.hidden = !items.length;
  }
  function pickSuggestion(i) {
    const it = suggestions[i]; if (!it) return;
    input.value = it.label; hideSuggest(); moveTo(it.lat, it.lon, { zoom: true });
  }
  input.addEventListener("input", () => {
    clearTimeout(suggestTimer);
    const q = input.value.trim();
    if (q.length < 3) return hideSuggest();
    suggestTimer = setTimeout(async () => {
      const seq = ++suggestSeq;
      const d = await quiet(api("suggest?q=" + encodeURIComponent(q)));
      if (seq === suggestSeq && input.value.trim() === q) renderSuggest(d?.results || []);
    }, 350);
  });
  input.addEventListener("keydown", e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!suggestions.length) return;
      e.preventDefault();
      sel = (sel + (e.key === "ArrowDown" ? 1 : -1) + suggestions.length) % suggestions.length;
      $$(".suggest-item", box).forEach((el, i) => el.classList.toggle("sel", i === sel));
    } else if (e.key === "Enter") {
      sel >= 0 ? pickSuggestion(sel) : search();
    } else if (e.key === "Escape") {
      hideSuggest(); input.blur();
    }
  });
  async function search() {
    const q = input.value.trim(); if (!q) return;
    hideSuggest();
    const d = await quiet(api("search", { query: q }));
    if (d?.ok) moveTo(d.lat, d.lon, { zoom: true });
    else toast(t(d?.error === "not_found" ? "not_found" : "network_error"));
  }
  $("#btn-search").onclick = search;
  document.addEventListener("click", e => { if (!e.target.closest(".search-wrap")) hideSuggest(); });

  // ---------- main controls ----------
  $("#btn-start").onclick = () => quiet(api("start", { lat: S.lat, lon: S.lon })).then(poll);
  $("#btn-stop").onclick = () => quiet(api("stop", {})).then(poll);
  $("#btn-center").onclick = () => map.setView([S.lat, S.lon], Math.max(map.getZoom(), 16));
  const copyCoords = () => navigator.clipboard?.writeText(fmtCoords(S.lat, S.lon)).then(() => toast(t("copied")), () => {});
  $("#btn-copy").onclick = copyCoords;
  $("#coords").onclick = copyCoords;

  // ---------- menu: the button expands into the panel / the panel compresses into the button ----------
  const sidebar = $("#sidebar"), pill = $("#menu-pill"), scroller = $("#sidebar-scroll");
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  function updatePillWidth() {
    sidebar.style.setProperty("--pill-w", Math.ceil($("span", pill).offsetWidth + 36) + "px");
  }
  function setMenu(open) {
    if (open === !sidebar.classList.contains("collapsed")) return;
    // Measure where we are now (possibly mid-animation) and where the CSS state ends.
    const from = sidebar.getBoundingClientRect(), fromRadius = getComputedStyle(sidebar).borderRadius;
    sidebar.getAnimations().forEach(a => a.cancel());
    scroller.getAnimations().forEach(a => a.cancel());
    sidebar.classList.toggle("collapsed", !open);
    scroller.inert = !open;
    pill.tabIndex = open ? -1 : 0;
    pill.setAttribute("aria-expanded", String(open));
    if (sidebar.__lg) {   // elastic "jelly" pull only while it is a small button, like the original
      sidebar.__lg.elasticity = open ? 0 : 0.15;
      sidebar.classList.toggle("lg-elastic", !open);
      sidebar.style.removeProperty("translate"); sidebar.style.removeProperty("scale");
    }
    if (reduceMotion.matches) return;
    const to = sidebar.getBoundingClientRect(), toRadius = getComputedStyle(sidebar).borderRadius;
    sidebar.animate(
      [{ width: from.width + "px", height: from.height + "px", borderRadius: fromRadius },
       { width: to.width + "px", height: to.height + "px", borderRadius: toRadius }],
      open ? { duration: 620, easing: "cubic-bezier(.3,1.25,.45,1)" }     // springy expand, slight overshoot
           : { duration: 440, easing: "cubic-bezier(.6,0,.3,1)" });       // quick, tight compress
    scroller.animate(open
      ? [{ opacity: 0, transform: "scale(.92)" }, { opacity: 1, transform: "none" }]
      : [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "scale(.92)" }],
      open ? { duration: 380, delay: 120, easing: "cubic-bezier(.2,.8,.2,1)", fill: "backwards" }
           : { duration: 200, easing: "ease-in" });
  }
  $("#btn-hide-bar").onclick = () => setMenu(false);
  pill.onclick = () => setMenu(true);

  // ---------- favorites ----------
  function renderFavorites() {
    const select = $("#fav-select"), folders = new Map();
    select.replaceChildren(new Option(t("choose_fav"), ""));
    S.favorites.forEach(f => {
      let parent = select;
      if (f.folder) {
        if (!folders.has(f.folder)) {
          const g = document.createElement("optgroup"); g.label = f.folder;
          folders.set(f.folder, select.appendChild(g));
        }
        parent = folders.get(f.folder);
      }
      parent.appendChild(new Option(f.name, f.id));
    });
    $("#fav-folders").replaceChildren(...[...folders.keys()].map(f => new Option(f)));
    $("#favs-count").textContent = S.favorites.length;
  }
  const setFavorites = d => { if (d?.favorites) { S.favorites = d.favorites; renderFavorites(); } return d; };
  const selectedFav = () => S.favorites.find(f => f.id === $("#fav-select").value);

  $("#btn-fav-save").onclick = async () => {
    await quiet(api("favorites", { name: $("#fav-name").value.trim(), folder: $("#fav-folder").value.trim(), lat: S.lat, lon: S.lon }).then(setFavorites));
    $("#fav-name").value = ""; toast(t("fav_saved"));
  };
  $("#btn-fav-go").onclick = () => { const f = selectedFav(); if (f) moveTo(f.lat, f.lon, { zoom: true }); };
  $("#fav-select").addEventListener("change", () => $("#btn-fav-go").click());
  $("#btn-fav-del").onclick = () => { const f = selectedFav(); if (f) quiet(api("favorites/" + encodeURIComponent(f.id), undefined, "DELETE").then(setFavorites)); };
  $("#btn-fav-export").onclick = async () => {
    const d = await quiet(api("favorites/export", {}));
    if (d?.ok) toast(t("saved_to", { path: d.path })); else if (!d?.cancelled) toast(t("save_failed"));
  };
  $("#btn-fav-import").onclick = () => $("#fav-file").click();
  $("#fav-file").onchange = async e => {
    const file = e.target.files[0]; e.target.value = "";
    if (!file) return;
    try {
      const d = setFavorites(await api("favorites/import", { favorites: JSON.parse(await file.text()) }));
      toast(t("favs_imported", { n: d.added }));
    } catch { toast(t("invalid_file")); }
  };

  // ---------- history ----------
  function ago(ts) {
    const m = Math.round((Date.now() / 1000 - ts) / 60);
    if (m < 1) return t("ago_now");
    if (m < 60) return t("ago_min", { n: m });
    if (m < 1440) return t("ago_h", { n: Math.round(m / 60) });
    return t("ago_d", { n: Math.round(m / 1440) });
  }
  function renderHistory() {
    $("#hist-count").textContent = S.history.length;
    $("#hist-list").replaceChildren(...S.history.slice(0, 8).map(h => {
      const row = document.createElement("div");
      row.className = "cell hist-cell";
      const a = document.createElement("span"), b = document.createElement("span");
      a.textContent = `${h.lat.toFixed(5)}, ${h.lon.toFixed(5)}`;
      b.className = "val"; b.textContent = ago(h.t);
      row.append(a, b);
      row.onclick = () => moveTo(h.lat, h.lon, { zoom: true });
      return row;
    }));
  }
  const loadHistory = () => quiet(api("history")).then(d => { if (d) { S.history = d.items || []; renderHistory(); } });
  $("#hist-sec").addEventListener("toggle", e => { if (e.target.open) loadHistory(); });
  $("#btn-hist-back").onclick = () => {
    const prev = S.history.find(h => distM(h, S) > 25);
    if (prev) { moveTo(prev.lat, prev.lon, { zoom: true }); toast(t("hist_back_done")); }
    else toast(t("hist_none"));
  };

  // ---------- keyboard & D-pad ----------
  document.addEventListener("keydown", e => {
    if (e.ctrlKey || e.altKey || e.metaKey || e.target.closest("input, select, textarea")) return;
    const k = e.key.toLowerCase();
    if (KEYS[k]) { e.preventDefault(); nudge(KEYS[k]); }
    else if (STEPS[k]) setStep(+k);
    else if (e.code === "Space") { e.preventDefault(); $("#btn-route-pause").click(); }
    else if (k === "escape" && S.adding) setAdding(false);
  });
  $$(".dpad .btn").forEach(b => {
    let timer;
    const stop = () => clearInterval(timer);
    b.addEventListener("pointerdown", () => { nudge(b.dataset.dir); timer = setInterval(() => nudge(b.dataset.dir), 140); });
    ["pointerup", "pointerleave", "pointercancel"].forEach(ev => b.addEventListener(ev, stop));
  });

  // ---------- status polling ----------
  const PHASE_CLASS = { idle: "idle", connecting: "busy", tunnel: "busy", mounting: "busy", active: "ok", error: "bad" };

  function renderStatus() {
    const st = S.last; if (!st) return;
    const { sim, device } = st;
    const phase = sim.enabled ? device.phase : (device.phase === "error" ? "error" : "idle");
    $("#status-pill").className = "status-pill " + PHASE_CLASS[phase];
    $("#status-text").textContent = t("st_" + phase);

    $("#device-line").textContent = device.name && device.connected
      ? t("dev_info", { name: device.name, ios: device.ios })
      : t(device.connected ? "dev_usb" : "dev_none");

    const err = device.error;
    $("#err-box").hidden = !err;
    if (err) {
      $("#err-text").textContent = t("err_" + err.code, { detail: err.detail });
      const action = $("#btn-err-action");
      action.hidden = !(err.code === "needs_admin" && !st.admin);
      action.textContent = t("restart_admin");
    }
    $("#btn-start").disabled = sim.enabled;
    $("#btn-stop").disabled = !sim.enabled;

    const r = sim.route;
    const cards = t("cardinals");
    let hdg = `<span class="arr" style="transform:rotate(${sim.heading}deg)">↑</span><span>${cards[Math.round(sim.heading / 45) % 8]} ${Math.round(sim.heading)}°</span>`;
    if (r.state === "running" || r.state === "paused") {
      hdg += `<span>${t("route_progress", { done: fmtDist(r.done_m), total: fmtDist(r.total_m), speed: r.state === "running" ? Math.round(r.speed_kmh) : 0 })}</span>`;
    }
    if (r.dwell_s > 0) hdg += `<span class="val">${t("dwelling", { s: r.dwell_s })}</span>`;
    if (hdg !== renderStatus.hdg) { $("#hdg").innerHTML = hdg; renderStatus.hdg = hdg; }  // numbers only - safe

    const pauseBtn = $("#btn-route-pause");
    setText(pauseBtn, t(r.state === "paused" ? "resume" : "pause"));
    pauseBtn.disabled = r.state !== "running" && r.state !== "paused";
    renderWizard();
  }

  function renderWizard() {
    if ($("#wizard").hidden || !S.last) return;
    const { device, sim } = S.last, code = device.error?.code;
    const mark = (id, cls) => { $(id).className = cls; };
    mark("#w-driver", code === "no_usbmuxd" ? "bad" : "ok");
    mark("#w-device", device.connected ? "ok" : (code === "trust_denied" ? "bad" : ""));
    mark("#w-devmode", code === "dev_mode_off" ? "bad" : (device.phase === "active" ? "ok" : ""));
    mark("#w-start", sim.enabled && device.phase === "active" ? "ok" : "");
  }

  let wasRouting = false;
  async function poll() {
    const st = await quiet(api("state"));
    if (!st) return;
    S.last = st;
    const { sim } = st;
    // Take the server position unless the user just moved the marker (avoids jumping back).
    if (sim.version !== S.serverVersion && Date.now() - S.localMoveAt > 700) {
      S.lat = sim.lat; S.lon = sim.lon;
      showPosition(false);
    }
    S.serverVersion = sim.version;
    const routing = sim.route.state === "running";
    if (wasRouting && sim.route.state === "done") toast(t("route_done"));
    wasRouting = routing;
    renderStatus();
  }

  function renderDynamic() {
    renderRouteInfo(); updateRouteStats(); renderFavorites(); renderHistory();
    $("#step-info").textContent = t("step_info", { m: STEPS[S.step] });
    renderStatus.hdg = null; renderStatus();
    $$(".segmented").forEach(placeThumb);
  }

  // ---------- wizard ----------
  const openWizard = () => { $("#wizard").hidden = false; renderWizard(); };
  $("#btn-help").onclick = openWizard;
  $("#btn-wiz-ok").onclick = () => { $("#wizard").hidden = true; store.set("wizard_seen", "1"); };
  $("#btn-err-action").onclick = () => quiet(api("elevate", {})).then(d => { if (!d?.ok) toast(t("elevate_failed")); });

  // ---------- liquid glass ----------
  LG.disabled = store.get("glass_off") === "1";
  $("#glass-effect").checked = !LG.disabled;
  $("#glass-effect").addEventListener("change", e => { store.set("glass_off", e.target.checked ? "0" : "1"); location.reload(); });
  // Full refraction only on surfaces that float over the map; inner controls get the
  // specular edges + hover/press highlights (refracting glass-on-glass costs GPU for no gain).
  LG.attach(sidebar, { refract: true, mode: "shader", displacement: 60, blur: 0.4, saturation: 165 });
  LG.attach($(".leaflet-bar"), { refract: true, displacement: 40, blur: 0.3, saturation: 165 });
  LG.attach($("#toast"), { refract: true, displacement: 50, blur: 0.3, saturation: 165 });
  LG.attach($(".wiz-card"), { refract: true, mode: "shader", displacement: 50, blur: 0.5, saturation: 165 });
  LG.attachAll(".card, .section, .search-wrap, .list, .segmented");
  LG.attachAll(".btn:not(.btn-plain)", { interactive: true, elasticity: 0.15 });

  // ---------- boot ----------
  setSeg("lang", lang);
  applyI18n();
  setStep(S.step);
  showPosition(false);
  redrawRoute();
  quiet(api("favorites")).then(setFavorites);
  loadHistory();
  if (!store.get("wizard_seen")) openWizard();
  poll();
  setInterval(() => { if (!document.hidden) poll(); }, 400);
})();
