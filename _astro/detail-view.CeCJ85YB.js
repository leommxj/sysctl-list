const h=new Map,$="/";function v(e){return`${$}data/${e}`}function f(e,a,t,o){const s=a.split("/").map(u=>encodeURIComponent(u)).join("/"),l=t&&o&&o>t?`#L${t}-L${o}`:t?`#L${t}`:"";return`https://github.com/torvalds/linux/blob/${encodeURIComponent(e)}/${s}${l}`}function r(e){return e.replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;")}function g(e){try{return new Intl.DateTimeFormat("en-US",{dateStyle:"medium"}).format(new Date(e))}catch{return e}}function D(){return c("catalog.json")}function k(){return c("versions.json")}function A(e){return c(`params/${e}.json`)}function m(e){return c(`blobs/${e}.json`)}function c(e){const a=v(e),t=h.get(a);if(t)return t;const o=fetch(a).then(async s=>{if(!s.ok)throw new Error(`Failed to load ${a}`);return await s.json()});return h.set(a,o),o}function b(e,a){if(!e.length)return"Unavailable";const t=e[0],o=e[e.length-1];return t===o?t:`${t}-${o===a?"latest":o}`}async function L(e){const{container:a,param:t,versions:o}=e,s=y(t,e.selectedVersion),l=o.at(-1)?.tag??s.tag,u=b(t.availableVersions,l),d=await Promise.all(s.docRefs.map(async n=>({...n,href:f(s.tag,n.path,n.lineStart,n.lineEnd),text:(await m(n.blob)).text})));a.innerHTML=`
    <div class="detail-header">
      <div class="detail-heading">
        <p class="detail-kicker">${r(t.namespace)}</p>
        <h2 class="detail-name">${r(t.name)}</h2>
      </div>
      <div class="detail-controls">
        <label class="field compact">
          <span>View version</span>
          <select data-role="version-select">
            ${t.versions.map(n=>`
                  <option value="${r(n.tag)}" ${n.tag===s.tag?"selected":""}>
                    ${r(n.tag)}
                  </option>
                `).join("")}
          </select>
        </label>
      </div>
    </div>
    <div class="detail-meta">
      <p class="availability-line">
        <span>Availability</span>
        <strong>${r(u)}</strong>
      </p>
    </div>
    <section class="panel inset detail-card">
      <div class="detail-section-head">
        <div>
          <h3>${r(s.tag)}</h3>
          <p class="version-caption">${r(S(o,s.tag))}</p>
        </div>
        <div class="status-row">
          <span class="status-pill ${s.supportStatus==="none"?"muted":"active"}">
            ${r(w(s.supportStatus))}
          </span>
          <span class="status-pill ${s.hasSource?"active":"muted"}">
            ${r(s.hasSource?"Source matched":"No source")}
          </span>
        </div>
      </div>
      ${d.length?d.map(n=>`
                  <article class="doc-card">
                    <header>
                      <strong>${r(n.heading)}</strong>
                      <a href="${r(n.href)}" target="_blank" rel="noreferrer">${r(j(n))}</a>
                    </header>
                    <pre>${r(n.text)}</pre>
                  </article>
                `).join(""):`<p class="empty-copy">${r(x(s.supportStatus,s.hasSource))}</p>`}
      ${s.sourceRefs.length?`
              <div class="source-list">
                <h4>Source facts</h4>
                ${s.sourceRefs.map(n=>`
                      <article class="source-card">
                        <header>
                          <a class="source-link" href="${r(f(s.tag,n.source_path))}" target="_blank" rel="noreferrer"><code>${r(n.source_path)}</code></a>
                        </header>
                        <dl class="source-facts">
                          ${i("api",n.api)}
                          ${i("table",n.table)}
                          ${i("path",n.path_segments.join(" / "))}
                          ${i("data",n.data_symbol)}
                          ${i("handler",n.handler_symbol)}
                        </dl>
                      </article>
                    `).join("")}
              </div>
            `:""}
    </section>
  `;const p=a.querySelector('[data-role="version-select"]');p?.addEventListener("change",()=>{e.onVersionChange?.(p.value)})}function y(e,a){return e.versions.find(t=>t.tag===a)??[...e.versions].reverse().find(t=>t.hasDoc||t.hasSource)??e.versions[e.versions.length-1]}function S(e,a){const t=e.find(o=>o.tag===a);return t?`${a} · ${g(t.releaseDate)}`:a}function w(e){switch(e){case"exact":return"Exact docs";case"context":return"Context docs";default:return"No docs"}}function x(e,a){return e==="none"&&a?"No Linux Documentation entry was found for this version.":"No documentation body captured for this version."}function j(e){return e.lineStart?e.lineEnd&&e.lineEnd>e.lineStart?`${e.path}:${e.lineStart}-${e.lineEnd}`:`${e.path}:${e.lineStart}`:e.path}function i(e,a){return a?`
    <div>
      <dt>${r(e)}</dt>
      <dd><code>${r(a)}</code></dd>
    </div>
  `:""}export{k as a,D as b,r as e,b as f,A as l,L as r};
