/* History: list, search, sort, view, delete */
(function () {
  const $ = (id) => document.getElementById(id);

  async function load() {
    const q = $("historySearch").value.trim();
    const order = $("historySort").value;
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (order) params.set("order", order);
    try {
      const { items } = await RIQ.api("/api/history?" + params.toString());
      const tb = $("historyBody"); tb.innerHTML = "";
      if (!items.length) {
        $("historyEmpty").classList.remove("hidden");
        return;
      }
      $("historyEmpty").classList.add("hidden");
      items.forEach(it => {
        const tr = document.createElement("tr");
        const date = new Date((it.created_at || "").replace(" ", "T") + "Z").toLocaleString();
        tr.innerHTML = `
          <td>${escapeHtml(it.filename)}</td>
          <td>${escapeHtml(it.job_title || "—")}</td>
          <td><strong>${Math.round(it.overall_score)}</strong></td>
          <td>${Math.round(it.ats_score)}</td>
          <td>${date}</td>
          <td class="row gap">
            <button class="btn ghost" data-view-id="${it.id}">View</button>
            <button class="btn ghost" data-pdf-id="${it.id}">PDF</button>
            <button class="icon-btn" data-del-id="${it.id}" title="Delete">🗑</button>
          </td>`;
        tb.appendChild(tr);
      });
    } catch (e) { RIQ.toast(e.message, "error"); }
  }

  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c])); }

  document.addEventListener("click", async (e) => {
    const v = e.target.closest("[data-view-id]");
    const d = e.target.closest("[data-del-id]");
    const p = e.target.closest("[data-pdf-id]");
    if (v) {
      try {
        const data = await RIQ.api("/api/history/" + v.dataset.viewId);
        RIQ.renderResults(data);
        document.querySelector('.nav-item[data-view="results"]').click();
      } catch (e) { RIQ.toast(e.message, "error"); }
    } else if (d) {
      if (!confirm("Delete this analysis?")) return;
      try {
        await RIQ.api("/api/history/" + d.dataset.delId, { method: "DELETE" });
        RIQ.toast("Deleted", "success"); load(); RIQ.loadStats && RIQ.loadStats();
      } catch (e) { RIQ.toast(e.message, "error"); }
    } else if (p) {
      try {
        const data = await RIQ.api("/api/history/" + p.dataset.pdfId);
        if (typeof RIQ.buildPdf === "function") RIQ.buildPdf(data);
        else window.location.href = "/api/report/" + p.dataset.pdfId;
      } catch (e) { RIQ.toast(e.message, "error"); }
    }
  });

  $("historySearch").addEventListener("input", load);
  $("historySort").addEventListener("change", load);
  RIQ.loadHistory = load;
})();
