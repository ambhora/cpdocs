// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 cpdocs developers
(() => {
  const root = document.documentElement;

  // Keep the sidebar where the reader left it; a full page load otherwise jumps it to the top.
  const sidebar = document.querySelector(".api-sidebar");
  const panelToggle = document.querySelector(".api-outline-panel-toggle");
  panelToggle?.addEventListener("click", () => {
    const open = sidebar?.classList.toggle("is-open") ?? false;
    panelToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) sidebar?.querySelector(".is-current")?.scrollIntoView({block: "nearest"});
  });
  if (sidebar) {
    try {
      const saved = sessionStorage.getItem("cpdocs-api-sidebar");
      if (saved !== null) sidebar.scrollTop = Number(saved);
    } catch {}
    const currentRow = sidebar.querySelector(".is-current");
    if (currentRow) {
      const box = sidebar.getBoundingClientRect();
      const row = currentRow.getBoundingClientRect();
      if (row.top < box.top || row.bottom > box.bottom) currentRow.scrollIntoView({block: "center"});
    }
    addEventListener("pagehide", () => {
      try { sessionStorage.setItem("cpdocs-api-sidebar", String(sidebar.scrollTop)); } catch {}
    });
  }

  document.querySelector(".api-theme")?.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    localStorage.setItem("cpdocs-api-theme", next);
  });

  // Drag the border of the outline or of the page contents to resize it; the width is kept for
  // later visits. Arrow keys resize a focused handle, double-click restores the default.
  for (const handle of document.querySelectorAll(".api-resizer")) {
    const side = handle.dataset.resize;
    const panel = document.querySelector(side === "sidebar" ? ".api-sidebar" : ".api-toc");
    const shell = handle.closest(".api-shell");
    if (!panel || !shell) continue;
    const property = `--api-${side}-width`;
    const key = `cpdocs-api-${side}-width`;
    const clamp = value => Math.round(Math.min(Math.max(value, 160), window.innerWidth * 0.45));
    const apply = width => root.style.setProperty(property, `${width}px`);
    const save = () => {
      try { localStorage.setItem(key, String(Math.round(panel.getBoundingClientRect().width))); } catch {}
    };
    handle.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      event.preventDefault();
      handle.setPointerCapture(event.pointerId);
      root.classList.add("is-resizing");
      const box = shell.getBoundingClientRect();
      const move = moving => apply(clamp(side === "sidebar" ? moving.clientX - box.left : box.right - moving.clientX));
      const stop = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", stop);
        handle.removeEventListener("pointercancel", stop);
        root.classList.remove("is-resizing");
        save();
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", stop);
      handle.addEventListener("pointercancel", stop);
    });
    handle.addEventListener("keydown", event => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const step = (event.shiftKey ? 64 : 16) * (event.key === "ArrowRight" ? 1 : -1);
      apply(clamp(panel.getBoundingClientRect().width + (side === "sidebar" ? step : -step)));
      save();
    });
    handle.addEventListener("dblclick", () => {
      root.style.removeProperty(property);
      try { localStorage.removeItem(key); } catch {}
    });
  }

  for (const button of document.querySelectorAll(".api-outline-toggle")) {
    const row = button.closest(".api-outline-row");
    const children = row?.nextElementSibling;
    if (!children?.classList.contains("api-outline-children")) continue;
    button.addEventListener("click", () => {
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", expanded ? "false" : "true");
      children.hidden = expanded;
    });
  }

  const version = document.querySelector(".api-version");
  const apiRoot = document.body.dataset.apiRoot || "../";
  const route = document.body.dataset.currentRoute || "";
  if (version) {
    fetch(apiRoot + "versions.json")
      .then(response => response.ok ? response.json() : null)
      .then(data => {
        if (!data?.versions) return;
        version.replaceChildren();
        for (const item of data.versions) {
          const option = document.createElement("option");
          option.value = item.name;
          option.textContent = item.name;
          option.selected = item.name === document.querySelector(".api-version")?.dataset.current;
          version.appendChild(option);
        }
        const current = location.pathname.split("/").filter(Boolean).at(-1);
        for (const option of version.options) {
          if (location.pathname.includes(`/${option.value}/`)) option.selected = true;
        }
        version.addEventListener("change", () => {
          location.href = apiRoot + version.value + "/" + route;
        });
      }).catch(() => {});
  }

  const search = document.querySelector(".api-search input");
  const results = document.querySelector(".api-search-results");
  const versionRoot = document.body.dataset.versionRoot || "./";
  let index = null;
  function showResults(values) {
    if (!results) return;
    results.replaceChildren();
    for (const item of values.slice(0, 20)) {
      // API names are data, not markup: C++ names such as operator< or a module named after an
      // arbitrary file name must reach the reader as text, so every value goes through textContent.
      const link = document.createElement("a");
      link.href = versionRoot + item.url;
      const label = document.createElement("strong");
      label.textContent = item.label;
      const detail = document.createElement("small");
      detail.textContent = `${item.kind} · ${item.qualified}`;
      link.append(label, document.createElement("br"), detail);
      results.appendChild(link);
    }
    results.hidden = values.length === 0;
  }
  search?.addEventListener("input", async () => {
    const query = search.value.trim().toLowerCase();
    if (!query) { if (results) results.hidden = true; return; }
    if (index === null) {
      try { index = await (await fetch(versionRoot + "search-index.json")).json(); }
      catch { index = []; }
    }
    const values = index.filter(item => `${item.label} ${item.qualified}`.toLowerCase().includes(query));
    showResults(values);
  });
  document.addEventListener("click", event => {
    if (!event.target.closest(".api-search") && results) results.hidden = true;
  });
})();
