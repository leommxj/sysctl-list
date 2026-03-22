import { loadParam, loadVersions } from "./browser-data";
import { renderParamDetail } from "./detail-view";

async function start(): Promise<void> {
  const pane = document.querySelector<HTMLElement>("#detailPagePane");
  const versionSelect = document.querySelector<HTMLSelectElement>("#detailVersion");

  if (!pane || !versionSelect) {
    return;
  }

  const detailPane = pane;
  const detailVersionSelect = versionSelect;
  const slug = detailPane.dataset.slug ?? "";
  const params = new URLSearchParams(window.location.search);
  const [param, versionPayload] = await Promise.all([loadParam(slug), loadVersions()]);

  let selectedVersion = params.get("version") ?? param.versions.at(-1)?.tag ?? versionPayload.versions.at(-1)?.tag ?? "";

  if (!param.versions.some((item) => item.tag === selectedVersion)) {
    selectedVersion = param.versions.at(-1)?.tag ?? versionPayload.versions.at(-1)?.tag ?? "";
  }

  detailVersionSelect.innerHTML = param.versions
    .map(
      (item) => `
        <option value="${item.tag}" ${item.tag === selectedVersion ? "selected" : ""}>
          ${item.tag}
        </option>
      `
    )
    .join("");

  async function refresh(): Promise<void> {
    await renderParamDetail({
      container: detailPane,
      onVersionChange: async (tag) => {
        selectedVersion = tag;
        detailVersionSelect.value = tag;
        updateUrl();
        await refresh();
      },
      param,
      selectedVersion,
      versions: versionPayload.versions
    });
  }

  function updateUrl(): void {
    const next = new URL(window.location.href);
    selectedVersion ? next.searchParams.set("version", selectedVersion) : next.searchParams.delete("version");
    history.replaceState({}, "", next);
  }

  detailVersionSelect.addEventListener("change", async () => {
    selectedVersion = detailVersionSelect.value;
    updateUrl();
    await refresh();
  });

  updateUrl();
  await refresh();
}

void start();
