/* Dashboard: upload, analyze, render results, profile */
(function () {
  const $ = (id) => document.getElementById(id);
  let selectedFile = null;
  let currentResult = null;
  let charts = {};

  // ---------- Upload ----------
  const dz = $("dropzone");
  const fileInput = $("fileInput");
  const filePreview = $("filePreview");

  function pickFile(f) {
    if (!f) return;
    const okExt = /\.(pdf|txt)$/i.test(f.name);
    if (!okExt) return RIQ.toast("Only PDF or TXT files are supported", "error");
    if (f.size > 8 * 1024 * 1024) return RIQ.toast("File too large (max 8 MB)", "error");
    selectedFile = f;
    $("fpName").textContent = f.name;
    $("fpSize").textContent = (f.size / 1024).toFixed(1) + " KB";
    filePreview.classList.remove("hidden");
  }
  dz.addEventListener("click", () => fileInput.click());
  $("browseBtn").addEventListener("click", (e) => { e.stopPropagation(); fileInput.click(); });
  fileInput.addEventListener("change", () => pickFile(fileInput.files[0]));
  ["dragenter", "dragover"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", e => { if (e.dataTransfer.files[0]) pickFile(e.dataTransfer.files[0]); });
  $("removeFile").addEventListener("click", () => {
    selectedFile = null; fileInput.value = ""; filePreview.classList.add("hidden");
  });

  // ---------- Job description ----------
  const jd = $("jobDesc");
  jd.addEventListener("input", () => $("charCount").textContent = jd.value.length);
  $("clearJD").addEventListener("click", () => { jd.value = ""; $("charCount").textContent = 0; });
  $("sampleJD").addEventListener("click", async () => {
    try {
      const s = await RIQ.api("/api/sample-jd");
      $("jobTitle").value = s.job_title;
      jd.value = s.job_description;
      $("charCount").textContent = jd.value.length;
    } catch (e) { RIQ.toast(e.message, "error"); }
  });

  // ---------- Analyze ----------
  $("analyzeBtn").addEventListener("click", async () => {
    if (!selectedFile) return RIQ.toast("Please choose a resume file first", "error");
    const fd = new FormData();
    fd.append("resume", selectedFile);
    fd.append("job_title", $("jobTitle").value || "");
    fd.append("job_description", jd.value || "");
    $("overlay").classList.remove("hidden");
    try {
      const data = await RIQ.api("/api/analyze", { method: "POST", body: fd });
      currentResult = data;
      renderResults(data);
      document.querySelector('.nav-item[data-view="results"]').click();
      RIQ.toast("Analysis complete", "success");
      loadStats();
    } catch (e) {
      RIQ.toast(e.message, "error");
    } finally {
      $("overlay").classList.add("hidden");
    }
  });

  // ---------- Results render ----------
  function renderResults(d) {
    $("resultsEmpty").classList.add("hidden");
    $("resultsContent").classList.remove("hidden");
    const s = d.scores;
    $("gNum").textContent = s.overall;
    $("gGrade").textContent = "Grade " + s.grade;
    $("gLevel").textContent = d.experience_level + " · " + (d.years_experience || 0) + " yrs experience";

    setBar("ATS", s.ats); setBar("Skill", s.skill);
    setBar("Exp", s.experience); setBar("Edu", s.education);

    renderGauge(s.overall);
    renderPie(d.skills_found);
    renderBar(d.skills_found);

    fillChips($("matchedSkills"), d.skills_matched, "good");
    fillChips($("missingSkills"), d.skills_missing, "miss");

    const tbody = $("gapBody"); tbody.innerHTML = "";
    d.skill_gap.forEach(g => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${escapeHtml(g.skill)}</strong><div class="muted small">${escapeHtml(g.category)}</div></td>
        <td><span class="badge ${g.priority}">${g.priority}</span></td>
        <td>${escapeHtml(g.learning_time)}</td>
        <td>${escapeHtml(g.career_impact)}</td>
        <td>${escapeHtml(g.difficulty)}</td>
        <td class="row gap">
          <a href="${g.docs}" target="_blank" rel="noopener" title="Docs">📚</a>
          <a href="${g.course}" target="_blank" rel="noopener" title="Course">🎓</a>
          <a href="${g.youtube}" target="_blank" rel="noopener" title="YouTube">▶</a>
          <a href="${g.practice}" target="_blank" rel="noopener" title="Practice">🧪</a>
        </td>`;
      tbody.appendChild(tr);
    });
    if (!d.skill_gap.length) tbody.innerHTML = `<tr><td colspan="6" class="muted center">No missing skills — great match!</td></tr>`;

    const plan = $("planList"); plan.innerHTML = "";
    d.improvement_plan.forEach(p => { const li = document.createElement("li"); li.textContent = p; plan.appendChild(li); });

    const roles = $("roleList"); roles.innerHTML = "";
    d.recommended_roles.forEach(r => { const c = document.createElement("span"); c.className = "chip role"; c.textContent = r; roles.appendChild(c); });
  }

  function setBar(key, v) {
    const fill = $("b" + key); const val = $("v" + key);
    requestAnimationFrame(() => { fill.style.width = v + "%"; });
    val.textContent = v;
  }
  function fillChips(host, dict, cls) {
    host.innerHTML = "";
    let any = false;
    Object.entries(dict).forEach(([cat, arr]) => {
      arr.forEach(s => {
        any = true;
        const span = document.createElement("span");
        span.className = "chip " + cls;
        span.textContent = s;
        host.appendChild(span);
      });
    });
    if (!any) host.innerHTML = `<span class="muted small">None.</span>`;
  }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c])); }

  // ---------- Charts ----------
  function renderGauge(value) {
    const ctx = $("gaugeChart").getContext("2d");
    if (charts.gauge) charts.gauge.destroy();
    charts.gauge = new Chart(ctx, {
      type: "doughnut",
      data: { datasets: [{ data: [value, 100 - value], backgroundColor: ["#7c5cff", "rgba(255,255,255,0.08)"], borderWidth: 0 }] },
      options: { cutout: "78%", plugins: { legend: { display: false }, tooltip: { enabled: false } }, animation: { animateRotate: true, duration: 1100 } }
    });
  }
  function renderPie(found) {
    const ctx = $("pieChart").getContext("2d");
    if (charts.pie) charts.pie.destroy();
    const labels = Object.keys(found);
    const data = labels.map(k => found[k].length);
    charts.pie = new Chart(ctx, {
      type: "pie",
      data: { labels, datasets: [{ data, backgroundColor: ["#7c5cff","#4dd0e1","#22c55e","#f59e0b","#ef4444","#06b6d4","#a855f7"], borderWidth: 0 }] },
      options: { plugins: { legend: { position: "bottom", labels: { color: getColor() } } } }
    });
  }
  function renderBar(found) {
    const ctx = $("barChart").getContext("2d");
    if (charts.bar) charts.bar.destroy();
    const labels = Object.keys(found);
    const data = labels.map(k => found[k].length);
    charts.bar = new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ data, backgroundColor: "#7c5cff", borderRadius: 8 }] },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: getColor() }, grid: { color: gridColor() } },
          y: { beginAtZero: true, ticks: { color: getColor() }, grid: { color: gridColor() } },
        },
      }
    });
  }
  function getColor() { return getComputedStyle(document.documentElement).getPropertyValue("--text").trim(); }
  function gridColor() { return getComputedStyle(document.documentElement).getPropertyValue("--border").trim(); }

  // ---------- PDF download ----------
  $("downloadPdf").addEventListener("click", () => {
    if (!currentResult) return RIQ.toast("Run an analysis first", "error");
    try {
      if (typeof RIQ.buildPdf === "function") {
        RIQ.buildPdf(currentResult);
      } else {
        window.location.href = "/api/report/" + currentResult.history_id;
      }
    } catch (e) {
      window.location.href = "/api/report/" + currentResult.history_id;
    }
  });

  // ---------- Stats ----------
  async function loadStats() {
    try {
      const { items } = await RIQ.api("/api/history");
      const total = items.length;
      const avg = total ? Math.round(items.reduce((a, b) => a + b.overall_score, 0) / total) : 0;
      const best = total ? Math.round(Math.max(...items.map(i => i.overall_score))) : 0;
      const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
      const recent = items.filter(i => new Date(i.created_at + "Z").getTime() >= weekAgo).length;
      RIQ.animateCounter($("stTotal"), total);
      RIQ.animateCounter($("stAvg"), avg);
      RIQ.animateCounter($("stBest"), best);
      RIQ.animateCounter($("stRecent"), recent);
    } catch (_) {}
  }
  loadStats();
  RIQ.loadStats = loadStats;
  RIQ.renderResults = renderResults;

  // ---------- Profile ----------
  $("saveProfile").addEventListener("click", async () => {
    try {
      await RIQ.api("/api/profile", { method: "POST", body: JSON.stringify({ name: $("pfName").value, email: $("pfEmail").value }) });
      $("userName").textContent = $("pfName").value;
      RIQ.toast("Profile updated", "success");
    } catch (e) { RIQ.toast(e.message, "error"); }
  });
  $("savePassword").addEventListener("click", async () => {
    try {
      await RIQ.api("/api/profile/password", { method: "POST", body: JSON.stringify({ old_password: $("pwOld").value, new_password: $("pwNew").value }) });
      $("pwOld").value = ""; $("pwNew").value = "";
      RIQ.toast("Password changed", "success");
    } catch (e) { RIQ.toast(e.message, "error"); }
  });
  $("uploadAvatar").addEventListener("click", () => $("avatarInput").click());
  $("avatarInput").addEventListener("change", async () => {
    const f = $("avatarInput").files[0];
    if (!f) return;
    if (f.size > 300 * 1024) return RIQ.toast("Image too large (max 300 KB)", "error");
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        await RIQ.api("/api/profile/avatar", { method: "POST", body: JSON.stringify({ avatar: reader.result }) });
        $("avatarBig").src = reader.result; $("avatarMini").src = reader.result;
        RIQ.toast("Avatar updated", "success");
      } catch (e) { RIQ.toast(e.message, "error"); }
    };
    reader.readAsDataURL(f);
  });
  $("deleteAccount").addEventListener("click", async () => {
    if (!confirm("This will permanently delete your account and all history. Continue?")) return;
    try {
      const d = await RIQ.api("/api/profile/delete", { method: "POST", body: "{}" });
      window.location.href = d.redirect || "/login";
    } catch (e) { RIQ.toast(e.message, "error"); }
  });
})();
