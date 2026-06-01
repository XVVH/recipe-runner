// table.js — sort, search, favorites filter
// Favorites are static (set in recipe frontmatter); no localStorage or toggling.
(function () {
  "use strict";

  const tbody    = document.getElementById("recipe-tbody");
  const searchEl = document.getElementById("search");
  const favBtn   = document.getElementById("fav-filter");
  const countEl  = document.getElementById("recipe-count");
  const emptyEl  = document.getElementById("empty-state");

  let sortKey = "date";
  let sortDir = "desc";
  let favOnly = false;
  let query   = "";

  const rows = () => Array.from(tbody.querySelectorAll("tr"));

  // ── Sort ──────────────────────────────────────────────────────────────────
  function sortRows() {
    const sorted = rows().sort((a, b) => {
      let av, bv;
      if (sortKey === "fav") {
        av = a.dataset.fav === "1" ? 1 : 0;
        bv = b.dataset.fav === "1" ? 1 : 0;
      } else {
        av = (a.dataset[sortKey] || "").toLowerCase();
        bv = (b.dataset[sortKey] || "").toLowerCase();
      }
      const cmp = typeof av === "number"
        ? av - bv
        : av.localeCompare(bv, undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
    sorted.forEach(r => tbody.appendChild(r));
    updateSortIndicators();
  }

  function updateSortIndicators() {
    document.querySelectorAll("thead th[data-col]").forEach(th => {
      th.classList.toggle("active", th.dataset.col === sortKey);
      const span = th.querySelector(".sort");
      if (span) span.textContent = sortDir === "asc" ? "▲" : "▼";
    });
  }

  document.querySelectorAll("thead th[data-col]").forEach(th => {
    th.addEventListener("click", () => {
      if (th.dataset.col === sortKey) sortDir = sortDir === "asc" ? "desc" : "asc";
      else { sortKey = th.dataset.col; sortDir = "asc"; }
      sortRows();
    });
  });

  // ── Filter ────────────────────────────────────────────────────────────────
  function applyFilter() {
    const q = query.trim().toLowerCase();
    let visible = 0;
    rows().forEach(r => {
      const matchSearch = !q || r.dataset.search.includes(q);
      const matchFav    = !favOnly || r.dataset.fav === "1";
      const show = matchSearch && matchFav;
      r.hidden = !show;
      if (show) visible++;
    });
    countEl.textContent = `${visible} ${visible === 1 ? "recipe" : "recipes"}`;
    emptyEl.hidden = visible > 0;
  }

  searchEl.addEventListener("input", () => { query = searchEl.value; applyFilter(); });

  favBtn.addEventListener("click", () => {
    favOnly = !favOnly;
    favBtn.classList.toggle("on", favOnly);
    applyFilter();
  });

  // ── Row click → recipe page ───────────────────────────────────────────────
  rows().forEach(r => {
    r.addEventListener("click", () => {
      window.location.href = "/" + r.dataset.slug + "/";
    });
  });

  // ── Init ──────────────────────────────────────────────────────────────────
  sortRows();
  applyFilter();
})();
