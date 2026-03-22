import { formatAvailabilityRange } from "./availability";
import { escapeHtml, loadCatalog, loadParam, loadVersions } from "./browser-data";
import { renderParamDetail } from "./detail-view";
import type { CatalogItem, ParamPayload } from "./types";

interface ExplorerState {
  namespace: string;
  query: string;
  selectedSlug: string;
  version: string;
}

const noDataText = "No data yet. Run sample extraction or build the full index.";
const noResultsText = "No matching parameters for the current search and filters.";
const rowHeight = 72;
const overscan = 6;
const sidebarStorageKey = "sysctl-explorer.sidebar-collapsed";

async function start(): Promise<void> {
  const workspace = document.querySelector<HTMLElement>("#workspace");
  const detailPane = document.querySelector<HTMLElement>("#detailPane");
  const searchInput = document.querySelector<HTMLInputElement>("#searchInput");
  const namespaceSelect = document.querySelector<HTMLSelectElement>("#namespaceSelect");
  const versionSelect = document.querySelector<HTMLSelectElement>("#versionSelect");
  const randomButton = document.querySelector<HTMLButtonElement>("#randomButton");
  const resultsCount = document.querySelector<HTMLElement>("#resultsCount");
  const sidebarToggle = document.querySelector<HTMLButtonElement>("#sidebarToggle");
  const listViewport = document.querySelector<HTMLElement>("#listViewport");
  const listSpacer = document.querySelector<HTMLElement>("#listSpacer");

  if (
    !workspace ||
    !detailPane ||
    !searchInput ||
    !namespaceSelect ||
    !versionSelect ||
    !randomButton ||
    !resultsCount ||
    !sidebarToggle ||
    !listViewport ||
    !listSpacer
  ) {
    return;
  }

  const ui = {
    detailPane,
    listSpacer,
    listViewport,
    namespaceSelect,
    randomButton,
    resultsCount,
    searchInput,
    sidebarToggle,
    versionSelect,
    workspace
  };

  const [catalogPayload, versionsPayload] = await Promise.all([loadCatalog(), loadVersions()]);
  const items = catalogPayload.items;
  const versions = versionsPayload.versions;
  const latestTag = versions.at(-1)?.tag ?? "";

  const params = new URLSearchParams(window.location.search);
  const state: ExplorerState = {
    namespace: params.get("ns") ?? "all",
    query: params.get("q") ?? "",
    selectedSlug: params.get("param") ?? "",
    version: params.get("version") ?? latestTag
  };

  if (!versions.some((item) => item.tag === state.version)) {
    state.version = latestTag;
  }

  let filtered: CatalogItem[] = [];
  let selectedParam: ParamPayload | null = null;
  let sidebarCollapsed = window.localStorage.getItem(sidebarStorageKey) === "true";

  const namespaces = ["all", ...new Set(items.map((item) => item.namespace))];
  namespaceSelect.innerHTML = namespaces
    .map(
      (value) => `
        <option value="${escapeHtml(value)}" ${state.namespace === value ? "selected" : ""}>
          ${escapeHtml(value === "all" ? "All namespaces" : value)}
        </option>
      `
    )
    .join("");
  versionSelect.innerHTML = versions
    .map(
      (version) => `
        <option value="${escapeHtml(version.tag)}" ${version.tag === state.version ? "selected" : ""}>
          ${escapeHtml(version.tag)}
        </option>
      `
    )
    .join("");
  searchInput.value = state.query;

  function updateUrl(): void {
    const next = new URL(window.location.href);
    state.query ? next.searchParams.set("q", state.query) : next.searchParams.delete("q");
    state.namespace !== "all" ? next.searchParams.set("ns", state.namespace) : next.searchParams.delete("ns");
    state.version ? next.searchParams.set("version", state.version) : next.searchParams.delete("version");
    state.selectedSlug ? next.searchParams.set("param", state.selectedSlug) : next.searchParams.delete("param");
    history.replaceState({}, "", next);
  }

  function syncSidebar(): void {
    ui.workspace.classList.toggle("sidebar-collapsed", sidebarCollapsed);
    ui.sidebarToggle.setAttribute("aria-expanded", String(!sidebarCollapsed));
    ui.sidebarToggle.setAttribute("aria-label", sidebarCollapsed ? "Show search panel" : "Hide search panel");
  }

  function searchItems(): CatalogItem[] {
    let pool = items;
    if (state.namespace !== "all") {
      pool = pool.filter((item) => item.namespace === state.namespace);
    }
    if (state.version) {
      pool = pool.filter((item) => item.availableVersions.includes(state.version));
    }
    const tokens = searchTokens(state.query);
    if (tokens.length) {
      pool = pool
        .filter((item) => matchesNameQuery(item.name, tokens))
        .sort((left, right) => compareNameQuery(left.name, right.name, tokens));
    }
    return pool;
  }

  function renderCount(): void {
    const suffix = filtered.length === 1 ? "result" : "results";
    ui.resultsCount.textContent = `${filtered.length} ${suffix}`;
  }

  function renderList(): void {
    filtered = searchItems();
    if (!filtered.length) {
      state.selectedSlug = "";
      ui.listSpacer.style.height = "0px";
      const emptyText = items.length ? noResultsText : noDataText;
      ui.listSpacer.innerHTML = `<p class="empty-copy">${escapeHtml(emptyText)}</p>`;
      ui.detailPane.innerHTML = "";
      renderCount();
      return;
    }
    if (!filtered.some((item) => item.slug === state.selectedSlug)) {
      state.selectedSlug = filtered[0].slug;
    }
    renderCount();
    const scrollTop = ui.listViewport.scrollTop;
    const viewportHeight = ui.listViewport.clientHeight || 720;
    const start = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
    const end = Math.min(filtered.length, Math.ceil((scrollTop + viewportHeight) / rowHeight) + overscan);
    ui.listSpacer.style.height = `${filtered.length * rowHeight}px`;
    ui.listSpacer.innerHTML = filtered
      .slice(start, end)
      .map((item, offset) => {
        const top = (start + offset) * rowHeight;
        const availability = formatAvailabilityRange(item.availableVersions, latestTag);
        return `
          <button
            class="list-row ${item.slug === state.selectedSlug ? "active" : ""}"
            data-slug="${escapeHtml(item.slug)}"
            style="top: ${top}px"
          >
            <div class="row-top">
              <strong>${escapeHtml(item.name)}</strong>
              <span>${escapeHtml(item.namespace)}</span>
            </div>
            <div class="row-meta">
              <small>${escapeHtml(`Availability ${availability}`)}</small>
            </div>
          </button>
        `;
      })
      .join("");
  }

  async function renderDetail(): Promise<void> {
    if (!state.selectedSlug) {
      selectedParam = null;
      ui.detailPane.innerHTML = "";
      return;
    }
    selectedParam = await loadParam(state.selectedSlug);
    await renderParamDetail({
      container: ui.detailPane,
      onVersionChange: async (tag) => {
        state.version = tag;
        ui.versionSelect.value = tag;
        updateUrl();
        renderList();
        await renderDetail();
      },
      param: selectedParam,
      selectedVersion: state.version,
      versions
    });
  }

  function refresh(): void {
    renderList();
    updateUrl();
    void renderDetail();
  }

  ui.listViewport.addEventListener("scroll", renderList);
  ui.listSpacer.addEventListener("click", (event) => {
    const target = event.target as HTMLElement;
    const row = target.closest<HTMLElement>("[data-slug]");
    if (!row) {
      return;
    }
    state.selectedSlug = row.dataset.slug ?? "";
    updateUrl();
    renderList();
    void renderDetail();
  });
  ui.searchInput.addEventListener("input", () => {
    state.query = ui.searchInput.value;
    ui.listViewport.scrollTop = 0;
    refresh();
  });
  ui.namespaceSelect.addEventListener("change", () => {
    state.namespace = ui.namespaceSelect.value;
    ui.listViewport.scrollTop = 0;
    refresh();
  });
  ui.versionSelect.addEventListener("change", () => {
    state.version = ui.versionSelect.value;
    ui.listViewport.scrollTop = 0;
    refresh();
  });
  ui.randomButton.addEventListener("click", () => {
    if (!filtered.length) {
      return;
    }
    const pick = filtered[Math.floor(Math.random() * filtered.length)];
    state.selectedSlug = pick.slug;
    updateUrl();
    renderList();
    void renderDetail();
  });
  ui.sidebarToggle.addEventListener("click", () => {
    sidebarCollapsed = !sidebarCollapsed;
    window.localStorage.setItem(sidebarStorageKey, String(sidebarCollapsed));
    syncSidebar();
  });

  syncSidebar();
  refresh();
}

void start();

function searchTokens(raw: string): string[] {
  const normalized = raw
    .trim()
    .toLowerCase()
    .replace(/^\/proc\/sys\//, "")
    .replaceAll("/", ".")
    .replace(/\s+/g, " ");
  return normalized ? normalized.split(" ") : [];
}

function matchesNameQuery(name: string, tokens: string[]): boolean {
  const normalized = name.toLowerCase();
  return tokens.every((token) => normalized.includes(token));
}

function compareNameQuery(left: string, right: string, tokens: string[]): number {
  return compareRank(rankName(left, tokens), rankName(right, tokens)) || left.localeCompare(right);
}

function rankName(name: string, tokens: string[]): [number, number, number] {
  const normalized = name.toLowerCase();
  const joined = tokens.join(" ");
  if (normalized === joined) {
    return [0, 0, normalized.length];
  }
  if (normalized.startsWith(joined)) {
    return [1, 0, normalized.length];
  }
  const firstIndex = Math.min(...tokens.map((token) => normalized.indexOf(token)));
  return [2, firstIndex, normalized.length];
}

function compareRank(left: number[], right: number[]): number {
  for (let index = 0; index < left.length; index += 1) {
    const diff = left[index] - right[index];
    if (diff) {
      return diff;
    }
  }
  return 0;
}
