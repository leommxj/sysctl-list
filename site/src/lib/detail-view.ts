import { formatAvailabilityRange } from "./availability";
import { escapeHtml, formatDate, loadBlob, upstreamPathHref } from "./browser-data";
import type { ParamPayload, ParamVersion, ReleaseVersion, SupportStatus } from "./types";

interface RenderOptions {
  container: HTMLElement;
  onVersionChange?: (tag: string) => void;
  param: ParamPayload;
  selectedVersion: string;
  versions: ReleaseVersion[];
}

export async function renderParamDetail(options: RenderOptions): Promise<void> {
  const { container, param, versions } = options;
  const current = pickVersion(param, options.selectedVersion);
  const latestTag = versions.at(-1)?.tag ?? current.tag;
  const availability = formatAvailabilityRange(param.availableVersions, latestTag);
  const docs = await Promise.all(
    current.docRefs.map(async (ref) => ({
      ...ref,
      href: upstreamPathHref(current.tag, ref.path, ref.lineStart, ref.lineEnd),
      text: (await loadBlob(ref.blob)).text
    }))
  );

  container.innerHTML = `
    <div class="detail-header">
      <div class="detail-heading">
        <p class="detail-kicker">${escapeHtml(param.namespace)}</p>
        <h2 class="detail-name">${escapeHtml(param.name)}</h2>
      </div>
      <div class="detail-controls">
        <label class="field compact">
          <span>View version</span>
          <select data-role="version-select">
            ${param.versions
              .map(
                (item) => `
                  <option value="${escapeHtml(item.tag)}" ${item.tag === current.tag ? "selected" : ""}>
                    ${escapeHtml(item.tag)}
                  </option>
                `
              )
              .join("")}
          </select>
        </label>
      </div>
    </div>
    <div class="detail-meta">
      <p class="availability-line">
        <span>Availability</span>
        <strong>${escapeHtml(availability)}</strong>
      </p>
    </div>
    <section class="panel inset detail-card">
      <div class="detail-section-head">
        <div>
          <h3>${escapeHtml(current.tag)}</h3>
          <p class="version-caption">${escapeHtml(formatVersionDate(versions, current.tag))}</p>
        </div>
        <div class="status-row">
          <span class="status-pill ${current.supportStatus === "none" ? "muted" : "active"}">
            ${escapeHtml(formatSupportLabel(current.supportStatus))}
          </span>
          <span class="status-pill ${current.hasSource ? "active" : "muted"}">
            ${escapeHtml(current.hasSource ? "Source matched" : "No source")}
          </span>
        </div>
      </div>
      ${
        docs.length
          ? docs
              .map(
                (doc) => `
                  <article class="doc-card">
                    <header>
                      <strong>${escapeHtml(doc.heading)}</strong>
                      <a href="${escapeHtml(doc.href)}" target="_blank" rel="noreferrer">${escapeHtml(formatDocPath(doc))}</a>
                    </header>
                    <pre>${escapeHtml(doc.text)}</pre>
                  </article>
                `
              )
              .join("")
          : `<p class="empty-copy">${escapeHtml(formatEmptyMessage(current.supportStatus, current.hasSource))}</p>`
      }
      ${
        current.sourceRefs.length
          ? `
              <div class="source-list">
                <h4>Source facts</h4>
                ${current.sourceRefs
                  .map(
                    (item) => `
                      <article class="source-card">
                        <header>
                          <a class="source-link" href="${escapeHtml(upstreamPathHref(current.tag, item.source_path))}" target="_blank" rel="noreferrer"><code>${escapeHtml(item.source_path)}</code></a>
                        </header>
                        <dl class="source-facts">
                          ${renderSourceFact("api", item.api)}
                          ${renderSourceFact("table", item.table)}
                          ${renderSourceFact("path", item.path_segments.join(" / "))}
                          ${renderSourceFact("data", item.data_symbol)}
                          ${renderSourceFact("handler", item.handler_symbol)}
                        </dl>
                      </article>
                    `
                  )
                  .join("")}
              </div>
            `
          : ""
      }
    </section>
  `;

  const select = container.querySelector<HTMLSelectElement>('[data-role="version-select"]');
  select?.addEventListener("change", () => {
    options.onVersionChange?.(select.value);
  });
}

function pickVersion(param: ParamPayload, selected: string): ParamVersion {
  return (
    param.versions.find((item) => item.tag === selected) ??
    [...param.versions].reverse().find((item) => item.hasDoc || item.hasSource) ??
    param.versions[param.versions.length - 1]
  );
}

function formatVersionDate(versions: ReleaseVersion[], tag: string): string {
  const version = versions.find((item) => item.tag === tag);
  if (!version) {
    return tag;
  }
  return `${tag} · ${formatDate(version.releaseDate)}`;
}

function formatSupportLabel(status: SupportStatus): string {
  switch (status) {
    case "exact":
      return "Exact docs";
    case "context":
      return "Context docs";
    default:
      return "No docs";
  }
}

function formatEmptyMessage(status: SupportStatus, hasSource: boolean): string {
  if (status === "none" && hasSource) {
    return "No Linux Documentation entry was found for this version.";
  }
  return "No documentation body captured for this version.";
}

function formatDocPath(doc: { lineEnd: number | null; lineStart: number | null; path: string }): string {
  if (!doc.lineStart) {
    return doc.path;
  }
  if (doc.lineEnd && doc.lineEnd > doc.lineStart) {
    return `${doc.path}:${doc.lineStart}-${doc.lineEnd}`;
  }
  return `${doc.path}:${doc.lineStart}`;
}

function renderSourceFact(label: string, value: string): string {
  if (!value) {
    return "";
  }
  return `
    <div>
      <dt>${escapeHtml(label)}</dt>
      <dd><code>${escapeHtml(value)}</code></dd>
    </div>
  `;
}
