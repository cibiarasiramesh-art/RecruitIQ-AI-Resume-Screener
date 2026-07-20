/* Auth pages: login & register */
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data;
  try { data = await res.json(); } catch (_) { data = {}; }
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function showToast(msg, type) {
  const t = document.getElementById("toast");
  if (!t) return;
  t.textContent = msg;
  t.className = "toast show " + (type || "");
  setTimeout(() => { t.className = "toast"; }, 2800);
}

const loginForm = document.getElementById("loginForm");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("loginError"); err.textContent = "";
    const fd = new FormData(loginForm);
    try {
      const data = await postJSON("/api/login", {
        email: fd.get("email"),
        password: fd.get("password"),
        remember: !!fd.get("remember"),
      });
      window.location.href = data.redirect || "/dashboard";
    } catch (e) { err.textContent = e.message; showToast(e.message, "error"); }
  });
}

const registerForm = document.getElementById("registerForm");
if (registerForm) {
  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("registerError"); err.textContent = "";
    const fd = new FormData(registerForm);
    try {
      const data = await postJSON("/api/register", {
        name: fd.get("name"),
        email: fd.get("email"),
        password: fd.get("password"),
      });
      window.location.href = data.redirect || "/dashboard";
    } catch (e) { err.textContent = e.message; showToast(e.message, "error"); }
  });
}
