/* Small, safe markdown renderer. Everything is HTML-escaped first; only known tags are produced. */
(function () {
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function inline(text, ctx) {
    const codes = [];
    let s = text.replace(/`([^`\n]+)`/g, (_, c) => { codes.push(c); return "\u0000" + (codes.length - 1) + "\u0000"; });
    s = s.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+|mailto:[^\s)]+)\)/g,
      (_, label, url) => '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + label + "</a>");
    s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g,
      (_, pre, url) => pre + '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + "</a>");
    s = s.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<em>$2</em>");
    s = s.replace(/(^|[^\w])_([^_\n]+)_(?!\w)/g, "$1<em>$2</em>");
    s = s.replace(/~~([^~\n]+)~~/g, "<del>$1</del>");
    if (ctx && ctx.handles) {
      s = s.replace(/(^|[^\w@])@([a-z0-9._-]+)/gi, (m, pre, h) =>
        ctx.handles.has(h.toLowerCase()) ? pre + '<span class="mention">@' + h + "</span>" : m);
    }
    if (ctx && ctx.keys) {
      s = s.replace(/(^|[^\w/#-])([A-Z][A-Z0-9]{1,9}-\d+)(?![\w-])/g, (m, pre, k) =>
        ctx.keys.has(k) ? pre + '<a href="#/item/' + k + '" class="keyref">' + k + "</a>" : m);
    }
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => "<code>" + codes[+i] + "</code>");
  }

  function render(src, ctx) {
    const lines = esc(src || "").replace(/\r\n?/g, "\n").split("\n");
    const out = [];
    let i = 0, para = [];
    const flush = () => { if (para.length) { out.push("<p>" + para.map(l => inline(l, ctx)).join("<br>") + "</p>"); para = []; } };
    while (i < lines.length) {
      const line = lines[i];
      if (/^```/.test(line)) {
        flush();
        const code = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
        i++;
        out.push("<pre><code>" + code.join("\n") + "</code></pre>");
        continue;
      }
      const h = line.match(/^(#{1,3})\s+(.*)$/);
      if (h) { flush(); const n = h[1].length + 2; out.push("<h" + n + ">" + inline(h[2], ctx) + "</h" + n + ">"); i++; continue; }
      if (/^&gt;\s?/.test(line)) {
        flush();
        const q = [];
        while (i < lines.length && /^&gt;\s?/.test(lines[i])) q.push(lines[i++].replace(/^&gt;\s?/, ""));
        out.push("<blockquote>" + q.map(l => inline(l, ctx)).join("<br>") + "</blockquote>");
        continue;
      }
      if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
        flush();
        const ordered = /^\s*\d+\./.test(line);
        const items = [];
        while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
          let t = lines[i].replace(/^\s*([-*]|\d+\.)\s+/, "");
          const task = t.match(/^\[( |x|X)\]\s+(.*)$/);
          if (task) {
            t = '<label class="task"><input type="checkbox" disabled' + (task[1] !== " " ? " checked" : "") + "> " + inline(task[2], ctx) + "</label>";
            items.push('<li class="task-li">' + t + "</li>");
          } else items.push("<li>" + inline(t, ctx) + "</li>");
          i++;
        }
        out.push((ordered ? "<ol>" : "<ul>") + items.join("") + (ordered ? "</ol>" : "</ul>"));
        continue;
      }
      if (/^\s*(---|\*\*\*)\s*$/.test(line)) { flush(); out.push("<hr>"); i++; continue; }
      if (!line.trim()) { flush(); i++; continue; }
      para.push(line);
      i++;
    }
    flush();
    return out.join("");
  }

  window.MD = { render, esc };
})();
