/* Europe AI Density — interactive density instrument.
   The population grid is the basemap: there are no map tiles, and a published page
   cannot fetch any, so cities are drawn from the raster itself. */
(function () {
  "use strict";

  const D = window.DENSITY_DATA;
  const EARTH_R = 6371.0088;
  const CANVAS = document.getElementById("map");
  const ctx = CANVAS.getContext("2d", { alpha: false });

  // ---- decode base64 typed arrays ------------------------------------------------
  function decode(b64, Type) {
    const bin = atob(b64);
    const buf = new ArrayBuffer(bin.length);
    const view = new Uint8Array(buf);
    for (let i = 0; i < bin.length; i++) view[i] = bin.charCodeAt(i);
    return new Type(buf);
  }
  function tier(t, step) {
    return {
      lat: decode(t.lat, Int16Array),
      lon: decode(t.lon, Int16Array),
      pop: decode(t.pop, Float32Array),
      step: step,
    };
  }
  const fine = tier(D.grid.fine, D.meta.fine_deg);
  const coarse = tier(D.grid.coarse, D.meta.coarse_deg);

  // ---- state ---------------------------------------------------------------------
  const state = {
    view: { lat: 48.95, lon: 8.25, zoom: 58 }, // zoom = px per degree of longitude
    sel: { lat: 48.53, lon: 9.06, r: 15 },
    threshold: 3,
    tiers: { T1: true, T2: true, T3: true },
    // How a person appointed in two cities is attributed. "all" counts them in full in
    // each, "split" divides them evenly, "primary" credits only their main employer.
    attribution: "all",
    showPreview: true,
    dragging: false,
  };

  function haversine(la1, lo1, la2, lo2) {
    const p1 = (la1 * Math.PI) / 180, p2 = (la2 * Math.PI) / 180;
    const dp = p2 - p1, dl = ((lo2 - lo1) * Math.PI) / 180;
    const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
    return 2 * EARTH_R * Math.asin(Math.sqrt(a));
  }

  // ---- projection ----------------------------------------------------------------
  // Equirectangular with a cos(lat) correction so Europe is not stretched sideways.
  let W = 0, H = 0, kx = 1, ky = 1;
  function resize() {
    const rect = CANVAS.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = Math.max(1, Math.round(rect.width));
    H = Math.max(1, Math.round(rect.height));
    CANVAS.width = W * dpr;
    CANVAS.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }
  function project(lat, lon) {
    const c = Math.cos((state.view.lat * Math.PI) / 180);
    kx = state.view.zoom;
    ky = state.view.zoom / c;
    return [W / 2 + (lon - state.view.lon) * kx, H / 2 - (lat - state.view.lat) * ky];
  }
  function unproject(x, y) {
    const c = Math.cos((state.view.lat * Math.PI) / 180);
    return [
      state.view.lat - (y - H / 2) / (state.view.zoom / c),
      state.view.lon + (x - W / 2) / state.view.zoom,
    ];
  }

  // ---- people --------------------------------------------------------------------
  function auditedPeople(city) {
    return D.audited[city].people.filter((p) => p.p >= state.threshold && state.tiers[p.t]);
  }
  // Weight of one person toward the city they were found in. Only adjudicated
  // cross-appointments carry a second city, so the switch moves nobody else.
  function weightOf(p) {
    if (!p.pc) return 1;
    if (state.attribution === "all") return 1;
    if (state.attribution === "split") return 1 / (p.nc || 2);
    return 0;
  }
  function auditedWeight(city) {
    return auditedPeople(city).reduce((a, p) => a + weightOf(p), 0);
  }
  function crossCount(city) {
    return auditedPeople(city).filter((p) => p.pc).length;
  }
  // Preview people all come from the CSRankings faculty layer, which is T1 by definition.
  function previewPeople(inst) {
    if (!state.tiers.T1) return [];
    return inst.pp.filter((e) => e[1] >= state.threshold);
  }
  function instCount(inst) { return previewPeople(inst).length; }
  const auditedCityOf = {};
  Object.keys(D.audited).forEach((c) => {
    auditedCityOf[c] = { lat: D.audited[c].lat, lon: D.audited[c].lon };
  });

  // Points drawn on the map. Audited cities are drawn from their own coordinates;
  // preview institutions from theirs. Provenance is encoded in the mark's form —
  // filled for audited, hollow for preview — so it survives greyscale and CVD.
  function mapPoints() {
    const pts = [];
    Object.keys(D.audited).forEach((city) => {
      const a = D.audited[city];
      if (a.lat == null) return;
      pts.push({ kind: "audited", label: city, lat: a.lat, lon: a.lon, n: auditedWeight(city) });
    });
    if (state.showPreview) {
      D.institutions.forEach((i) => {
        // An audited city already has its own mark; drawing its institutions again
        // would read as two clusters where there is one.
        if (isCoveredByAudited(i)) return;
        const n = instCount(i);
        if (n > 0) pts.push({ kind: "preview", label: i.n, lat: i.lat, lon: i.lon, n: n, city: i.city });
      });
    }
    return pts;
  }

  // ---- selection maths -----------------------------------------------------------
  function populationWithin(lat, lon, r) {
    let total = 0, cells = 0;
    const dLat = r / 111.0 + 0.05;
    const dLon = dLat / Math.max(0.2, Math.cos((lat * Math.PI) / 180));
    for (const t of [fine, coarse]) {
      const s = t.step;
      const laMin = (lat - dLat) / s, laMax = (lat + dLat) / s;
      const loMin = (lon - dLon) / s, loMax = (lon + dLon) / s;
      for (let i = 0; i < t.pop.length; i++) {
        const la = t.lat[i], lo = t.lon[i];
        if (la < laMin || la > laMax || lo < loMin || lo > loMax) continue;
        const cLat = la * s, cLon = lo * s;
        if (haversine(lat, lon, cLat, cLon) <= r) { total += t.pop[i]; cells++; }
      }
      // The fine tier covers every populated area near an institution; the coarse tier
      // only fills in elsewhere, so counting both would double-count nothing — the two
      // are disjoint by construction.
    }
    return { pop: total, cells: cells };
  }

  function selectionStats() {
    const { lat, lon, r } = state.sel;
    let people = 0, audited = 0, preview = 0;
    const inRange = [];
    Object.keys(D.audited).forEach((city) => {
      const a = D.audited[city];
      if (a.lat == null) return;
      if (haversine(lat, lon, a.lat, a.lon) <= r) {
        const n = auditedWeight(city);
        audited += n; people += n;
        inRange.push({ kind: "audited", label: city, n: n, status: D.audited[city].status });
      }
    });
    if (state.showPreview) {
      D.institutions.forEach((i) => {
        if (haversine(lat, lon, i.lat, i.lon) > r) return;
        // An audited city's own institutions are already counted in its roster.
        if (isCoveredByAudited(i)) return;
        const n = instCount(i);
        if (n > 0) {
          preview += n; people += n;
          inRange.push({ kind: "preview", label: i.n, n: n, city: i.city });
        }
      });
    }
    const { pop, cells } = populationWithin(lat, lon, r);
    inRange.sort((a, b) => b.n - a.n);
    return { people, audited, preview, pop, cells, inRange };
  }

  function rosterRows() {
    const { lat, lon, r } = state.sel;
    const rows = [];
    Object.keys(D.audited).forEach((city) => {
      const a = D.audited[city];
      if (a.lat == null || haversine(lat, lon, a.lat, a.lon) > r) return;
      auditedPeople(city).forEach((p) =>
        rows.push({ name: p.n, papers: p.p, tier: p.t, where: city, primary: p.pc || "",
                    weight: weightOf(p), kind: "audited", src: p.s.join(" · ") }));
    });
    if (state.showPreview) {
      D.institutions.forEach((i) => {
        if (isCoveredByAudited(i) || haversine(lat, lon, i.lat, i.lon) > r) return;
        previewPeople(i).forEach((e) =>
          rows.push({ name: e[0], papers: e[1], tier: "T1", where: i.city || i.n,
                      primary: "", weight: 1, kind: "preview", src: "csrankings" }));
      });
    }
    rows.sort((a, b) => b.papers - a.papers);
    return rows;
  }

  const AUDITED_INSTS = new Set([
    "University of Tübingen", "Saarland University", "CISPA Helmholtz Center",
    "University of Stuttgart", "TU Kaiserslautern",
  ]);
  function isCoveredByAudited(i) { return AUDITED_INSTS.has(i.n); }

  // ---- drawing -------------------------------------------------------------------
  const css = getComputedStyle(document.documentElement);
  function token(name) { return css.getPropertyValue(name).trim(); }

  function popColor(v, alpha) {
    // Sequential, one hue, light to dark within the theme's direction.
    const dark = document.documentElement.dataset.theme === "dark" ||
      (!document.documentElement.dataset.theme &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    const t = Math.min(1, Math.log10(1 + v) / 4.6);
    if (dark) {
      const l = 12 + t * 72;
      return `hsla(196, ${30 + t * 25}%, ${l}%, ${alpha})`;
    }
    const l = 92 - t * 62;
    return `hsla(200, ${20 + t * 40}%, ${l}%, ${alpha})`;
  }

  function draw() {
    const bg = token("--surface-map");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    // population raster — the basemap
    for (const t of [coarse, fine]) {
      const s = t.step;
      const w = Math.max(1, s * state.view.zoom);
      const h = Math.max(1, (s * state.view.zoom) / Math.cos((state.view.lat * Math.PI) / 180));
      for (let i = 0; i < t.pop.length; i++) {
        const [x, y] = project(t.lat[i] * s, t.lon[i] * s);
        if (x < -w || x > W + w || y < -h || y > H + h) continue;
        ctx.fillStyle = popColor(t.pop[i], 1);
        ctx.fillRect(x - w / 2, y - h / 2, w, h);
      }
    }

    // selection disc
    const [sx, sy] = project(state.sel.lat, state.sel.lon);
    const rPx = (state.sel.r / 111.0) * (state.view.zoom / Math.cos((state.view.lat * Math.PI) / 180));
    ctx.save();
    ctx.beginPath();
    ctx.arc(sx, sy, rPx, 0, Math.PI * 2);
    ctx.fillStyle = token("--sel-fill");
    ctx.fill();
    ctx.setLineDash([6, 5]);
    ctx.lineWidth = 2;
    ctx.strokeStyle = token("--sel-stroke");
    ctx.stroke();
    ctx.restore();

    // Label the circle with its own radius. Without it the control feels detached at
    // low zoom, where 15 km and 60 km are both only a few pixels across.
    if (rPx > 14) {
      ctx.save();
      ctx.font = "600 10px ui-monospace, SFMono-Regular, Menlo, monospace";
      ctx.textAlign = "center";
      ctx.lineWidth = 3;
      ctx.strokeStyle = token("--surface-map");
      ctx.strokeText(state.sel.r + " km", sx, sy - rPx - 5);
      ctx.fillStyle = token("--sel-stroke");
      ctx.fillText(state.sel.r + " km", sx, sy - rPx - 5);
      ctx.restore();
    }

    // institution / city marks
    const pts = mapPoints();
    for (const p of pts) {
      const [x, y] = project(p.lat, p.lon);
      if (x < -20 || x > W + 20 || y < -20 || y > H + 20) continue;
      const rad = Math.max(4, Math.min(22, 3 + Math.sqrt(p.n) * 2.2));
      ctx.beginPath();
      ctx.arc(x, y, rad, 0, Math.PI * 2);
      if (p.kind === "audited") {
        ctx.fillStyle = token("--series-audited");
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = token("--surface-map");
        ctx.stroke();
      } else {
        ctx.lineWidth = 2;
        ctx.strokeStyle = token("--series-preview");
        ctx.stroke();
      }
    }

    // label the audited cities, which are few enough to name directly
    ctx.font = "600 11px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.textAlign = "center";
    for (const p of pts) {
      if (p.kind !== "audited") continue;
      const [x, y] = project(p.lat, p.lon);
      const rad = Math.max(4, Math.min(22, 3 + Math.sqrt(p.n) * 2.2));
      ctx.lineWidth = 3;
      ctx.strokeStyle = token("--surface-map");
      ctx.strokeText(p.label, x, y - rad - 6);
      ctx.fillStyle = token("--ink");
      ctx.fillText(p.label, x, y - rad - 6);
    }
    drawScaleBar();
    updateReadout();
  }

  function drawScaleBar() {
    const pxPerKm = state.view.zoom / (111.0 * Math.cos((state.view.lat * Math.PI) / 180));
    const targets = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
    let km = targets[targets.length - 1];
    for (const t of targets) if (t * pxPerKm >= 60) { km = t; break; }
    const len = km * pxPerKm;
    const x = 14, y = H - 16;
    ctx.save();
    ctx.lineWidth = 2;
    ctx.strokeStyle = token("--surface-map");
    ctx.beginPath();
    ctx.moveTo(x, y); ctx.lineTo(x + len, y);
    ctx.moveTo(x, y - 4); ctx.lineTo(x, y + 4);
    ctx.moveTo(x + len, y - 4); ctx.lineTo(x + len, y + 4);
    ctx.stroke();
    ctx.lineWidth = 1;
    ctx.strokeStyle = token("--ink");
    ctx.stroke();
    ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.textAlign = "left";
    ctx.fillStyle = token("--ink");
    ctx.fillText(km + " km", x + len + 7, y + 3.5);
    ctx.restore();
  }

  // ---- readout -------------------------------------------------------------------
  const fmt = (n, d) => n.toLocaleString("en-GB", { maximumFractionDigits: d === undefined ? 0 : d });
  function updateReadout() {
    const s = selectionStats();
    const per100k = s.pop > 0 ? (1e5 * s.people) / s.pop : 0;
    document.getElementById("r-density").textContent = s.pop > 0 ? per100k.toFixed(2) : "—";
    document.getElementById("r-people").textContent =
      Number.isInteger(s.people) ? fmt(s.people) : s.people.toFixed(1);
    document.getElementById("r-pop").textContent = fmt(s.pop);
    const cross = Object.keys(D.audited).reduce((a, c) => {
      const x = D.audited[c];
      return a + (x.lat != null &&
        haversine(state.sel.lat, state.sel.lon, x.lat, x.lon) <= state.sel.r ? crossCount(c) : 0);
    }, 0);
    document.getElementById("r-split").textContent =
      (Number.isInteger(s.audited) ? s.audited : s.audited.toFixed(1)) +
      " audited \u00b7 " + s.preview + " preview" +
      (cross ? " \u00b7 " + cross + " cross-appointed" : "");
    document.getElementById("r-where").textContent =
      state.sel.lat.toFixed(3) + ", " + state.sel.lon.toFixed(3) + " · r " + state.sel.r + " km";

    const list = document.getElementById("r-list");
    list.innerHTML = "";
    s.inRange.slice(0, 14).forEach((e) => {
      const li = document.createElement("li");
      li.className = "inrange " + e.kind;
      li.innerHTML =
        '<span class="mark" aria-hidden="true"></span>' +
        '<span class="nm">' + escapeHtml(e.label) + "</span>" +
        '<span class="ct">' + e.n + "</span>";
      list.appendChild(li);
    });
    renderRoster();
    if (!s.inRange.length) {
      const li = document.createElement("li");
      li.className = "inrange empty";
      li.textContent = "Nothing in range — drag the circle onto a cluster.";
      list.appendChild(li);
    }
  }
  let rosterLimit = 120;
  function renderRoster() {
    const rows = rosterRows();
    const tb = document.getElementById("roster-body");
    const cap = document.getElementById("roster-count");
    tb.innerHTML = "";
    cap.textContent = rows.length
      ? rows.length + (rows.length > rosterLimit ? " people · showing " + rosterLimit : " people")
      : "nothing in range";
    rows.slice(0, rosterLimit).forEach((r) => {
      const tr = document.createElement("tr");
      if (r.weight === 0) tr.className = "muted-row";
      tr.innerHTML =
        "<td class='name'><span class='dot " + r.kind + "'></span>" + escapeHtml(r.name) + "</td>" +
        "<td class='num strong'>" + r.papers + "</td>" +
        "<td><span class='tier t-" + r.tier + "'>" + r.tier + "</span></td>" +
        "<td class='prov'>" + escapeHtml(r.where) +
          (r.primary ? " <span class='xa'>\u2192 " + escapeHtml(r.primary) + "</span>" : "") + "</td>" +
        "<td class='prov src'>" + escapeHtml(r.src) + "</td>";
      tb.appendChild(tr);
    });
    const more = document.getElementById("roster-more");
    more.hidden = rows.length <= rosterLimit;
  }
  document.getElementById("roster-more").addEventListener("click", () => {
    rosterLimit += 200;
    renderRoster();
  });

  function escapeHtml(t) {
    return t.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ---- ranking table -------------------------------------------------------------
  function clusterRows() {
    const rows = [];
    Object.keys(D.audited).forEach((city) => {
      const a = D.audited[city];
      if (a.lat == null) return;
      const n = auditedWeight(city);
      if (!n) return;
      const { pop } = populationWithin(a.lat, a.lon, 15);
      rows.push({ name: city, kind: "audited", n, pop, status: a.status });
    });
    // Preview clusters: institutions within 10 km of each other, named for the largest.
    const insts = D.institutions.filter((i) => instCount(i) > 0 && !isCoveredByAudited(i));
    const used = new Array(insts.length).fill(false);
    for (let i = 0; i < insts.length; i++) {
      if (used[i]) continue;
      const group = [i];
      used[i] = true;
      for (let j = i + 1; j < insts.length; j++) {
        if (used[j]) continue;
        if (haversine(insts[i].lat, insts[i].lon, insts[j].lat, insts[j].lon) < 10) {
          used[j] = true; group.push(j);
        }
      }
      const n = group.reduce((acc, k) => acc + instCount(insts[k]), 0);
      if (n < 5) continue;
      const lead = group.reduce((a, b) => (instCount(insts[a]) >= instCount(insts[b]) ? a : b));
      const { pop } = populationWithin(insts[lead].lat, insts[lead].lon, 15);
      rows.push({ name: insts[lead].city || insts[lead].n, kind: "preview", n, pop, status: "csrankings only" });
    }
    rows.forEach((r) => (r.per100k = r.pop > 0 ? (1e5 * r.n) / r.pop : 0));
    return rows;
  }

  let sortKey = "per100k";
  function renderTable() {
    const rows = clusterRows().sort((a, b) => b[sortKey] - a[sortKey]);
    const tb = document.getElementById("rank-body");
    tb.innerHTML = "";
    rows.slice(0, 40).forEach((r, idx) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        "<td class='rank'>" + (idx + 1) + "</td>" +
        "<td class='name'><span class='dot " + r.kind + "'></span>" + escapeHtml(r.name) + "</td>" +
        "<td class='num'>" + (Number.isInteger(r.n) ? r.n : r.n.toFixed(1)) + "</td>" +
        "<td class='num'>" + fmt(r.pop) + "</td>" +
        "<td class='num strong'>" + r.per100k.toFixed(2) + "</td>" +
        "<td class='prov'>" + r.status + "</td>";
      tb.appendChild(tr);
    });
    drawScatter(rows);
  }

  // ---- scatter: count against population, log-log, iso-density diagonals ----------
  function drawScatter(rows) {
    const c = document.getElementById("scatter");
    const g = c.getContext("2d");
    const rect = c.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(rect.width)), h = Math.max(1, Math.round(rect.height));
    c.width = w * dpr; c.height = h * dpr;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);

    const pad = { l: 52, r: 14, t: 14, b: 34 };
    const pts = rows.filter((r) => r.pop > 0 && r.n > 0);
    if (!pts.length) return;
    const xMin = 4.4, xMax = 7.4;              // log10 population
    const yMin = 0, yMax = Math.log10(260);    // log10 people
    const X = (v) => pad.l + ((Math.log10(v) - xMin) / (xMax - xMin)) * (w - pad.l - pad.r);
    const Y = (v) => h - pad.b - ((Math.log10(v) - yMin) / (yMax - yMin)) * (h - pad.t - pad.b);

    // iso-density diagonals: constant people per 100k
    g.setLineDash([3, 4]);
    g.lineWidth = 1;
    g.strokeStyle = token("--line");
    g.fillStyle = token("--muted");
    g.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
    [1, 3, 10, 30].forEach((d) => {
      g.beginPath();
      let first = true;
      for (let lx = xMin; lx <= xMax; lx += 0.1) {
        const pop = Math.pow(10, lx);
        const people = (d * pop) / 1e5;
        if (people < 1 || people > 260) { first = true; continue; }
        const x = X(pop), y = Y(people);
        if (first) { g.moveTo(x, y); first = false; } else g.lineTo(x, y);
      }
      g.stroke();
      const pop = Math.pow(10, xMax - 0.02);
      const people = (d * pop) / 1e5;
      if (people >= 1 && people <= 260) {
        g.textAlign = "right";
        g.fillText(d + "/100k", X(pop), Y(people) - 4);
      }
    });
    g.setLineDash([]);

    // axes
    g.strokeStyle = token("--line");
    g.beginPath();
    g.moveTo(pad.l, pad.t); g.lineTo(pad.l, h - pad.b); g.lineTo(w - pad.r, h - pad.b);
    g.stroke();
    g.fillStyle = token("--muted");
    g.textAlign = "center";
    [[1e5, "100k"], [1e6, "1M"], [1e7, "10M"]].forEach(([v, lab]) => {
      if (Math.log10(v) < xMin || Math.log10(v) > xMax) return;
      g.fillText(lab, X(v), h - pad.b + 14);
    });
    g.textAlign = "right";
    [1, 10, 100].forEach((v) => g.fillText(String(v), pad.l - 6, Y(v) + 3));
    g.save();
    g.translate(12, h / 2); g.rotate(-Math.PI / 2); g.textAlign = "center";
    g.fillText("PIs in cluster", 0, 0);
    g.restore();
    g.textAlign = "center";
    g.fillText("population within 15 km", pad.l + (w - pad.l - pad.r) / 2, h - 6);

    // marks — audited filled, preview hollow, so identity is not colour-alone
    pts.forEach((r) => {
      const x = X(r.pop), y = Y(r.n);
      g.beginPath();
      g.arc(x, y, r.kind === "audited" ? 5.5 : 4, 0, Math.PI * 2);
      if (r.kind === "audited") {
        g.fillStyle = token("--series-audited"); g.fill();
        g.lineWidth = 2; g.strokeStyle = token("--surface"); g.stroke();
      } else {
        g.lineWidth = 1.5; g.strokeStyle = token("--series-preview"); g.stroke();
      }
    });
    g.fillStyle = token("--ink");
    g.font = "600 10px ui-monospace, SFMono-Regular, Menlo, monospace";
    pts.filter((r) => r.kind === "audited").forEach((r) => {
      g.textAlign = "left";
      g.fillText(r.name, X(r.pop) + 9, Y(r.n) + 3);
    });
  }

  // ---- interaction ---------------------------------------------------------------
  CANVAS.addEventListener("pointerdown", (e) => {
    state.dragging = true;
    CANVAS.setPointerCapture(e.pointerId);
    moveSel(e);
  });
  CANVAS.addEventListener("pointermove", (e) => { if (state.dragging) moveSel(e); });
  CANVAS.addEventListener("pointerup", () => { state.dragging = false; });
  function moveSel(e) {
    const rect = CANVAS.getBoundingClientRect();
    const [lat, lon] = unproject(e.clientX - rect.left, e.clientY - rect.top);
    state.sel.lat = lat; state.sel.lon = lon;
    draw();
  }
  CANVAS.addEventListener("wheel", (e) => {
    e.preventDefault();
    const rect = CANVAS.getBoundingClientRect();
    const before = unproject(e.clientX - rect.left, e.clientY - rect.top);
    state.view.zoom = Math.max(6, Math.min(900, state.view.zoom * (e.deltaY < 0 ? 1.18 : 1 / 1.18)));
    const after = unproject(e.clientX - rect.left, e.clientY - rect.top);
    state.view.lat += before[0] - after[0];
    state.view.lon += before[1] - after[1];
    draw();
  }, { passive: false });

  const rSlider = document.getElementById("radius");
  rSlider.addEventListener("input", () => {
    state.sel.r = Number(rSlider.value);
    document.getElementById("radius-val").textContent = state.sel.r + " km";
    // At a continental zoom a 15 km circle and a 60 km circle are both a handful of
    // pixels, so the control reads as broken even though the geometry is right. Rather
    // than draw the circle at a fake size, move the camera so the real one is legible.
    const cos = Math.cos((state.view.lat * Math.PI) / 180);
    const rPx = (state.sel.r / 111.0) * (state.view.zoom / cos);
    const lo = 26, hi = Math.min(W, H) * 0.42;
    if (rPx < lo || rPx > hi) {
      const want = Math.max(lo, Math.min(hi, Math.min(W, H) * 0.3));
      state.view.zoom = Math.max(6, Math.min(900, (want * 111.0 * cos) / state.sel.r));
      state.view.lat = state.sel.lat;
      state.view.lon = state.sel.lon;
    }
    draw();
  });
  document.querySelectorAll("[data-threshold]").forEach((b) => {
    b.addEventListener("click", () => {
      state.threshold = Number(b.dataset.threshold);
      document.querySelectorAll("[data-threshold]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      draw(); renderTable();
    });
  });
  document.querySelectorAll("[data-tier]").forEach((b) => {
    b.addEventListener("click", () => {
      const t = b.dataset.tier;
      state.tiers[t] = !state.tiers[t];
      b.setAttribute("aria-pressed", String(state.tiers[t]));
      draw(); renderTable();
    });
  });

  document.querySelectorAll("[data-attr]").forEach((b) => {
    b.addEventListener("click", () => {
      state.attribution = b.dataset.attr;
      document.querySelectorAll("[data-attr]").forEach((x) =>
        x.setAttribute("aria-pressed", String(x === b)));
      draw(); renderTable();
    });
  });

  const prevToggle = document.getElementById("toggle-preview");
  prevToggle.addEventListener("change", () => {
    state.showPreview = prevToggle.checked;
    draw(); renderTable();
  });
  document.querySelectorAll("[data-goto]").forEach((b) => {
    b.addEventListener("click", () => {
      const [lat, lon, zoom, r] = b.dataset.goto.split(",").map(Number);
      state.view.lat = lat; state.view.lon = lon; state.view.zoom = zoom;
      state.sel.lat = lat; state.sel.lon = lon; state.sel.r = r;
      rSlider.value = String(r);
      document.getElementById("radius-val").textContent = r + " km";
      draw();
    });
  });
  document.querySelectorAll("[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      sortKey = th.dataset.sort;
      document.querySelectorAll("[data-sort]").forEach((x) =>
        x.setAttribute("aria-sort", x === th ? "descending" : "none"));
      renderTable();
    });
  });

  window.addEventListener("resize", () => { resize(); renderTable(); });
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", () => { draw(); renderTable(); });
  new MutationObserver(() => { draw(); renderTable(); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // ---- go ------------------------------------------------------------------------
  document.getElementById("meta-snapshot").textContent = D.meta.snapshot;
  document.getElementById("meta-window").textContent = D.meta.window;
  resize();
  renderTable();
})();
