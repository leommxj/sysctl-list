import{l as u,a as g,r as m}from"./detail-view.CeCJ85YB.js";async function w(){const i=document.querySelector("#detailPagePane"),c=document.querySelector("#detailVersion");if(!i||!c)return;const l=i,s=c,d=l.dataset.slug??"",v=new URLSearchParams(window.location.search),[n,t]=await Promise.all([u(d),g()]);let a=v.get("version")??n.versions.at(-1)?.tag??t.versions.at(-1)?.tag??"";n.versions.some(e=>e.tag===a)||(a=n.versions.at(-1)?.tag??t.versions.at(-1)?.tag??""),s.innerHTML=n.versions.map(e=>`
        <option value="${e.tag}" ${e.tag===a?"selected":""}>
          ${e.tag}
        </option>
      `).join("");async function o(){await m({container:l,onVersionChange:async e=>{a=e,s.value=e,r(),await o()},param:n,selectedVersion:a,versions:t.versions})}function r(){const e=new URL(window.location.href);a?e.searchParams.set("version",a):e.searchParams.delete("version"),history.replaceState({},"",e)}s.addEventListener("change",async()=>{a=s.value,r(),await o()}),r(),await o()}w();
