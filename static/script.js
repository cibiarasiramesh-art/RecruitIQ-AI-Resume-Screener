/* Shared helpers: toast, theme persistence, navigation */
(function () {
  const saved = localStorage.getItem("riq-theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
})();

window.RIQ = window.RIQ || {};
RIQ.toast = function (msg, type) {
  const t = document.getElementById("toast");
  if (!t) return;
  t.textContent = msg;
  t.className = "toast show " + (type || "");
  clearTimeout(RIQ._toastT);
  RIQ._toastT = setTimeout(() => { t.className = "toast"; }, 3000);
};

RIQ.api = async function (url, opts = {}) {
  const res = await fetch(url, {
    credentials: "same-origin",
    headers: opts.body && !(opts.body instanceof FormData)
      ? { "Content-Type": "application/json", ...(opts.headers || {}) }
      : (opts.headers || {}),
    ...opts,
  });
  if (res.status === 401) {
    window.location.href = "/login";
    return;
  }
  let data;
  try { data = await res.json(); } catch (_) { data = {}; }
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
};

// Sidebar navigation
document.addEventListener("click", (e) => {
  const item = e.target.closest(".nav-item");
  if (!item) return;
  const view = item.dataset.view;
  document.querySelectorAll(".nav-item").forEach(n => n.classList.toggle("active", n === item));
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + view));
  if (view === "history" && typeof RIQ.loadHistory === "function") RIQ.loadHistory();
});

// Theme toggle
const themeBtn = document.getElementById("themeToggle");
if (themeBtn) {
  themeBtn.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", cur);
    localStorage.setItem("riq-theme", cur);
    themeBtn.textContent = cur === "dark" ? "🌙 Toggle theme" : "☀ Toggle theme";
  });
}

// Animated counters
function animateCounter(el, target) {
  const start = +el.dataset.counter || 0;
  const dur = 900;
  const t0 = performance.now();
  function step(now) {
    const p = Math.min(1, (now - t0) / dur);
    const v = Math.round(start + (target - start) * (1 - Math.pow(1 - p, 3)));
    el.textContent = v;
    if (p < 1) requestAnimationFrame(step);
    else el.dataset.counter = target;
  }
  requestAnimationFrame(step);
}
RIQ.animateCounter = animateCounter;
