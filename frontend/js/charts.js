/* Dependency-free SVG charts. Colours come from CSS classes (.c0 ... .c7) so themes apply. */
(function () {
  const W = 640, H = 220, L = 36, R = 12, T = 12, B = 28;
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const niceMax = v => { if (v <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))); const n = v / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p; };
  const short = d => { const [, m, day] = String(d).split("-"); return day ? +day + "/" + +m : d; };

  function frame(labels, max, label) {
    const plotW = W - L - R, plotH = H - T - B;
    let s = "";
    for (let i = 0; i <= 4; i++) {
      const y = T + plotH - (plotH * i) / 4;
      s += '<line class="grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + y + '" y2="' + y + '"/>';
      s += '<text class="tick" x="' + (L - 6) + '" y="' + (y + 4) + '" text-anchor="end">' + +((max * i) / 4).toFixed(2) + "</text>";
    }
    const step = Math.max(1, Math.ceil(labels.length / 8)), last = labels.length - 1;
    labels.forEach((lab, i) => {
      if (i !== last && (i % step || last - i < step * 0.6)) return;
      const x = L + (labels.length === 1 ? plotW / 2 : (plotW * i) / (labels.length - 1));
      s += '<text class="tick" x="' + x + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(label ? label(lab) : short(lab)) + "</text>";
    });
    return s;
  }
  const xAt = (i, n) => L + (n === 1 ? (W - L - R) / 2 : ((W - L - R) * i) / (n - 1));
  const yAt = (v, max) => T + (H - T - B) - ((H - T - B) * v) / max;
  const legend = series => '<div class="legend">' + series.map((s, i) =>
    '<span><i class="sw ' + (s.cls || "c" + i) + (s.dash ? " dash" : "") + '"></i>' + esc(s.name) + "</span>").join("") + "</div>";
  const wrap = (svg, series, title) => '<figure class="chart"><svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(title || "Chart") + '">' + svg + "</svg>" + (series ? legend(series) : "") + "</figure>";

  function line(opts) {
    const { labels, series } = opts;
    const vals = series.flatMap(s => s.values.filter(v => v != null));
    const max = niceMax(Math.max(1, ...vals));
    let svg = frame(labels, max);
    series.forEach((s, si) => {
      let d = "", started = false;
      s.values.forEach((v, i) => {
        if (v == null) { started = false; return; }
        d += (started ? "L" : "M") + xAt(i, labels.length).toFixed(1) + " " + yAt(v, max).toFixed(1) + " ";
        started = true;
      });
      svg += '<path class="ln ' + (s.cls || "c" + si) + (s.dash ? " dash" : "") + '" d="' + d + '"/>';
      if (!s.dash) s.values.forEach((v, i) => {
        if (v != null && (labels.length <= 16 || v !== 0)) svg += '<circle class="pt ' + (s.cls || "c" + si) + '" r="2.5" cx="' + xAt(i, labels.length).toFixed(1) + '" cy="' + yAt(v, max).toFixed(1) + '"><title>' + esc(s.name + " " + labels[i] + ": " + v) + "</title></circle>";
      });
    });
    return wrap(svg, series, opts.title);
  }

  function bars(opts) {
    const { labels, series } = opts;
    const max = niceMax(Math.max(1, ...series.flatMap(s => s.values)));
    const plotW = W - L - R, groupW = plotW / Math.max(1, labels.length), barW = Math.min(28, (groupW * 0.7) / series.length);
    let svg = "";
    for (let i = 0; i <= 4; i++) {
      const y = yAt((max * i) / 4, max);
      svg += '<line class="grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + y + '" y2="' + y + '"/><text class="tick" x="' + (L - 6) + '" y="' + (y + 4) + '" text-anchor="end">' + +((max * i) / 4).toFixed(2) + "</text>";
    }
    labels.forEach((lab, i) => {
      const gx = L + groupW * i + groupW / 2;
      series.forEach((s, si) => {
        const v = s.values[i] || 0, x = gx - (barW * series.length) / 2 + barW * si, y = yAt(v, max);
        svg += '<rect class="vbar ' + (s.cls || "c" + si) + '" x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + (barW - 2).toFixed(1) + '" height="' + (T + H - T - B - y).toFixed(1) + '" rx="2"><title>' + esc(lab + ", " + s.name + ": " + v) + "</title></rect>";
      });
      svg += '<text class="tick" x="' + gx + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(String(lab).slice(0, 14)) + "</text>";
    });
    return wrap(svg, series, opts.title);
  }

  function stacked(opts) {
    const { labels, series } = opts;
    const n = labels.length, totals = labels.map((_, i) => series.reduce((a, s) => a + (s.values[i] || 0), 0));
    const max = niceMax(Math.max(1, ...totals));
    let svg = frame(labels, max);
    const base = new Array(n).fill(0);
    const layers = series.map(s => { const lo = base.slice(); s.values.forEach((v, i) => (base[i] += v || 0)); return { s, lo, hi: base.slice() }; });
    layers.slice().reverse().forEach(({ s, lo, hi }) => {
      const si = series.indexOf(s);
      let d = "M" + xAt(0, n) + " " + yAt(hi[0], max);
      for (let i = 1; i < n; i++) d += " L" + xAt(i, n).toFixed(1) + " " + yAt(hi[i], max).toFixed(1);
      for (let i = n - 1; i >= 0; i--) d += " L" + xAt(i, n).toFixed(1) + " " + yAt(lo[i], max).toFixed(1);
      svg += '<path class="area ' + (s.cls || "c" + si) + '" d="' + d + ' Z"><title>' + esc(s.name) + "</title></path>";
    });
    return wrap(svg, series, opts.title);
  }

  function scatter(opts) {
    const pts = opts.points, labels = opts.labels;
    const max = niceMax(Math.max(1, ...pts.map(p => p.y)));
    let svg = frame(labels, max);
    const idx = Object.fromEntries(labels.map((l, i) => [l, i]));
    pts.forEach(p => {
      const i = idx[p.x];
      if (i == null) return;
      svg += '<circle class="pt big c0" r="4" cx="' + xAt(i, labels.length).toFixed(1) + '" cy="' + yAt(p.y, max).toFixed(1) + '"><title>' + esc(p.label + ": " + p.y + " days") + "</title></circle>";
    });
    if (opts.avg) svg += '<line class="ln c1 dash" x1="' + L + '" x2="' + (W - R) + '" y1="' + yAt(opts.avg, max) + '" y2="' + yAt(opts.avg, max) + '"/>';
    return wrap(svg, [{ name: "Work item", cls: "c0" }, { name: "Average " + opts.avg + " days", cls: "c1", dash: true }], opts.title);
  }

  window.Charts = { line, bars, stacked, scatter };
})();
