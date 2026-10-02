(() => {
  const SCHOLAR = "https://scholar.google.com/citations?user=IPrRziQAAAAJ&hl=en";
  const ME = /\b((M\.?|Muhammad)\s+Adnan)\b/gi;

  // nav state + footer year
  const page = document.body.dataset.page;
  document.querySelectorAll("nav a").forEach(a => {
    if (a.dataset.page === page) a.setAttribute("aria-current", "page");
  });
  document.querySelectorAll("[data-year]").forEach(el => (el.textContent = new Date().getFullYear()));

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDate = d => d ? new Date(d + "T00:00:00Z").toLocaleDateString("en-GB",
    { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }) : null;

  let cache;
  const load = () => cache ??= fetch("data/publications.json", { cache: "no-cache" })
    .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });

  // ---------- home metrics ----------
  const metrics = document.getElementById("metrics");
  if (metrics) {
    load().then(d => {
      const p = d.profile || {};
      const items = [
        ["Citations", p.citations],
        ["h-index", p.h_index],
        ["i10-index", p.i10_index],
        ["Publications", d.publications?.length || null],
      ].filter(([, v]) => v != null);
      if (!items.length) return;
      metrics.querySelector("dl").innerHTML = items
        .map(([k, v]) => `<div><dt>${k}</dt><dd>${Number(v).toLocaleString("en")}</dd></div>`).join("");
      const when = fmtDate(d.updated);
      metrics.querySelector(".metrics-note").innerHTML =
        `From <a href="${SCHOLAR}">Google Scholar</a>${when ? `, updated ${when}` : ""}.`;
      metrics.hidden = false;
    }).catch(() => {});
  }

  // ---------- publications page ----------
  const list = document.getElementById("pub-list");
  if (!list) return;
  const q = document.getElementById("pub-search");
  const yearSel = document.getElementById("pub-year");
  const count = document.getElementById("pub-count");
  let all = [];

  const item = p => {
    const title = p.url ? `<a href="${esc(p.url)}">${esc(p.title)}</a>` : esc(p.title);
    const authors = p.authors ? `<p class="pub-authors">${esc(p.authors).replace(ME, "<strong>$1</strong>")}</p>` : "";
    const venue = p.venue ? `<p class="pub-venue">${esc(p.venue)}</p>` : "";
    const links = [
      p.doi && `<a href="https://doi.org/${esc(p.doi)}">DOI</a>`,
      p.citations ? `<span>Cited by ${p.citations}</span>` : "",
    ].filter(Boolean).join("");
    return `<li><p class="pub-title">${title}</p>${authors}${venue}${links ? `<p class="pub-links">${links}</p>` : ""}</li>`;
  };

  const render = () => {
    const term = q.value.trim().toLowerCase();
    const yr = yearSel.value;
    const rows = all.filter(p =>
      (!yr || String(p.year ?? "") === yr) &&
      (!term || `${p.title} ${p.authors} ${p.venue}`.toLowerCase().includes(term)));
    count.textContent = `${rows.length} of ${all.length} publications`;
    if (!rows.length) {
      list.innerHTML = `<div class="empty"><p>No publications match “${esc(q.value)}”.</p><p>Try a shorter search or choose all years.</p></div>`;
      return;
    }
    const groups = new Map();
    rows.forEach(p => {
      const k = p.year || "Undated";
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(p);
    });
    list.innerHTML = [...groups].map(([y, ps]) =>
      `<section class="pub-year"><h2>${esc(y)}</h2><ol>${ps.map(item).join("")}</ol></section>`).join("");
  };

  load().then(d => {
    all = d.publications || [];
    const note = document.getElementById("pub-updated");
    const when = fmtDate(d.updated);
    if (note && when) note.textContent = `Last synced ${when}${d.source && d.source !== "Google Scholar" ? ` (via ${d.source})` : ""}.`;
    if (!all.length) throw new Error("empty");
    [...new Set(all.map(p => p.year).filter(Boolean))].sort((a, b) => b - a)
      .forEach(y => yearSel.add(new Option(y, y)));
    document.querySelector(".pub-tools").hidden = false;
    q.addEventListener("input", render);
    yearSel.addEventListener("change", render);
    render();
  }).catch(() => {
    list.innerHTML = `<div class="empty">
      <p>The publication list hasn't been synced yet.</p>
      <p>Meanwhile, see the full list on <a href="${SCHOLAR}">Google Scholar</a>.</p></div>`;
  });
})();
