/* Client-side PDF generation via jsPDF UMD */
(function () {
  RIQ.buildPdf = function (data) {
    if (!window.jspdf) {
      window.location.href = "/api/report/" + (data.history_id || "");
      return;
    }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ unit: "pt", format: "a4" });
    const W = doc.internal.pageSize.getWidth();
    const H = doc.internal.pageSize.getHeight();
    let y = 40;

    function addHeader() {
      doc.setFillColor(124, 92, 255);
      doc.rect(0, 0, W, 78, "F");
      doc.setTextColor(255, 255, 255);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(24);
      doc.text("RecruitIQ", 40, 38);
      doc.setFontSize(11);
      doc.setFont("helvetica", "normal");
      doc.text("Resume Intelligence Report", 40, 58);
      doc.text(new Date().toLocaleString(), W - 200, 58);
      y = 105;
    }

    function section(title) {
      if (y > 740) { doc.addPage(); y = 50; }
      doc.setFillColor(245, 247, 255);
      doc.roundedRect(36, y - 8, W - 72, 24, 6, 6, "F");
      doc.setTextColor(86, 72, 155);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(13);
      doc.text(title, 48, y + 6);
      y += 28;
      doc.setTextColor(15, 23, 42);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(11);
    }

    function bullets(arr) {
      arr.forEach((t) => {
        const lines = doc.splitTextToSize("• " + t, W - 92);
        lines.forEach((l) => {
          if (y > 780) { doc.addPage(); y = 50; }
          doc.text(l, 52, y);
          y += 14;
        });
      });
      y += 4;
    }

    addHeader();
    doc.setTextColor(15, 23, 42);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.text((data.candidate || "Candidate") + " — Resume Summary", 40, y);
    y += 18;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(11);
    doc.text("File: " + (data.filename || "—"), 40, y); y += 14;
    if (data.job_title) { doc.text("Job: " + data.job_title, 40, y); y += 14; }
    doc.text("Experience: " + (data.experience_level || "—") + " (" + (data.years_experience || 0) + " yrs)", 40, y); y += 18;

    const s = data.scores || {};
    section("Score overview");
    const scoreRows = [
      ["Overall", s.overall + " (Grade " + (s.grade || "—") + ")"],
      ["ATS Match", s.ats],
      ["Skills", s.skill],
      ["Experience", s.experience],
      ["Education", s.education],
    ];
    scoreRows.forEach(([k, v]) => {
      doc.text(k, 52, y);
      doc.text(String(v), 220, y);
      const pct = typeof v === "number" ? v : parseFloat(String(v)) || 0;
      doc.setFillColor(237, 240, 255);
      doc.rect(280, y - 8, 240, 8, "F");
      doc.setFillColor(124, 92, 255);
      doc.rect(280, y - 8, 240 * Math.min(100, pct) / 100, 8, "F");
      y += 16;
    });
    y += 8;

    section("Matched skills");
    const matched = flatten(data.skills_matched);
    bullets(matched.length ? matched : ["No skills matched yet."]);

    section("Missing skills");
    const missing = flatten(data.skills_missing);
    bullets(missing.length ? missing : ["No gaps detected."]);

    section("Skill gap intelligence");
    (data.skill_gap || []).forEach((g) => {
      bullets([`${g.skill} — ${g.priority || "Medium"} priority · ${g.learning_time || "—"} · ${g.difficulty || "—"}`]);
    });
    if (!data.skill_gap || !data.skill_gap.length) bullets(["No gaps detected."]);

    section("Improvement plan");
    bullets(data.improvement_plan || []);

    section("Recommended roles");
    bullets(data.recommended_roles || []);

    doc.save("RecruitIQ_Report.pdf");
  };

  function flatten(dict) {
    const out = [];
    Object.entries(dict || {}).forEach(([cat, arr]) => arr.forEach((s) => out.push(`${s}  (${cat})`)));
    return out;
  }
})();
