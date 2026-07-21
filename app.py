"""
RecruitIQ - AI-Powered Resume Intelligence Platform
Flask backend with SQLite, resume parsing, ATS scoring, and PDF reports.
"""
import os
import re
import io
import json
import sqlite3
import secrets
from datetime import datetime
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect, url_for, session,
    jsonify, send_file, flash, g
)
from authlib.integrations.flask_client import OAuth
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from services.recruitiq_ai import analyze_resume as ai_analyzer
from models.custom_resume_model import MODEL_PATH, load_model, predict_resume_match

# ----------------------------------------------------------------------
# App configuration
# ----------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
REPORT_FOLDER = os.path.join(BASE_DIR, "reports")
ASSET_FOLDER = os.path.join(BASE_DIR, "assets")
DB_PATH = os.path.join(BASE_DIR, "database.db")
ALLOWED_EXTENSIONS = {"pdf", "txt"}
MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)
os.makedirs(os.path.join(ASSET_FOLDER, "icons"), exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_COOKIE_SECURE"] = False
app.config["SESSION_COOKIE_DOMAIN"] = None

from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5000/auth/google/callback")
GOOGLE_AUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
GOOGLE_AUTH_STATUS = "configured" if GOOGLE_AUTH_ENABLED else "not_configured"

oauth = OAuth(app)
if GOOGLE_AUTH_ENABLED:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile"
        }
    )


def set_session_user(user_id, user_name):
    session["user_id"] = user_id
    session["user_name"] = user_name


# ----------------------------------------------------------------------
# Database helpers
# ----------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            avatar TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            job_title TEXT DEFAULT '',
            overall_score REAL DEFAULT 0,
            ats_score REAL DEFAULT 0,
            skill_score REAL DEFAULT 0,
            education_score REAL DEFAULT 0,
            experience_score REAL DEFAULT 0,
            data_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            history_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(history_id) REFERENCES history(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY,
            theme TEXT DEFAULT 'dark',
            notifications INTEGER DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()
    conn.close()


init_db()
import os
import re
import io
import json
from dotenv import load_dotenv
load_dotenv()

# ----------------------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/") and not request.path.startswith("/api/report/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    return db.execute(
        "SELECT id, name, email, avatar, created_at FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def create_or_update_google_user(email, name, avatar=""):
    db = get_db()
    email = (email or "").strip().lower()
    name = (name or "User").strip()
    row = db.execute("SELECT id, name, avatar FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        db.execute(
            "UPDATE users SET name = ?, avatar = ? WHERE id = ?",
            (name or row["name"], avatar or row["avatar"], row["id"]),
        )
        db.commit()
        return row["id"]
    password_hash = generate_password_hash(secrets.token_hex(16))
    cur = db.execute(
        "INSERT INTO users (name, email, password, avatar) VALUES (?, ?, ?, ?)",
        (name, email, password_hash, avatar),
    )
    db.commit()
    return cur.lastrowid


def normalize_skill_payload(payload, fallback=None):
    if isinstance(payload, dict):
        normalized = {}
        for category, skills in payload.items():
            if isinstance(skills, (list, tuple, set)):
                normalized[str(category)] = [str(skill) for skill in skills]
            else:
                normalized[str(category)] = []
        return normalized
    if isinstance(payload, (list, tuple, set)):
        return {"General": [str(skill) for skill in payload]}
    return fallback or {}


def build_ai_payload(ai_result, fallback_result):
    if not isinstance(ai_result, dict):
        ai_result = {}
    payload = dict(ai_result)

    def normalize_skills(value, fallback=None):
        if isinstance(value, dict):
            return {str(k): [str(skill) for skill in v] if isinstance(v, (list, tuple, set)) else [] for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return {"General": [str(skill) for skill in value]}
        return fallback or {}

    payload.setdefault("ats_score", ai_result.get("ats", 0))
    payload.setdefault("recommendation", "Needs Improvement")
    payload.setdefault("skill_match_percentage", 0)

    matched = normalize_skills(ai_result.get("matched_skills"), ai_result.get("skills_matched"))
    missing = normalize_skills(ai_result.get("missing_skills"), ai_result.get("skills_missing"))
    payload["matched_skills"] = matched or normalize_skills(fallback_result.get("matched_skills") if isinstance(fallback_result, dict) else None)
    payload["missing_skills"] = missing or normalize_skills(fallback_result.get("missing_skills") if isinstance(fallback_result, dict) else None)

    payload.setdefault("learning_roadmap", ai_result.get("improvement_plan", []))
    payload.setdefault("improvement_plan", payload.get("learning_roadmap", []))
    if not payload.get("learning_roadmap") and isinstance(fallback_result, dict):
        payload["learning_roadmap"] = fallback_result.get("improvement_plan", [])
        payload["improvement_plan"] = fallback_result.get("improvement_plan", [])
    return payload


# ----------------------------------------------------------------------
# Skill knowledge base
# ----------------------------------------------------------------------
SKILL_DB = {
    "Programming Languages": [
        "python", "java", "javascript", "typescript", "c", "c++", "c#",
        "go", "rust", "ruby", "php", "swift", "kotlin", "scala", "r",
        "dart", "perl", "objective-c", "matlab", "bash",
    ],
    "Frameworks": [
        "react", "next.js", "nextjs", "angular", "vue", "svelte",
        "django", "flask", "fastapi", "express", "spring", "spring boot",
        "laravel", "rails", "asp.net", "nestjs", "nuxt", "ember",
    ],
    "Libraries": [
        "tensorflow", "pytorch", "keras", "numpy", "pandas", "scikit-learn",
        "matplotlib", "seaborn", "opencv", "jquery", "redux", "rxjs",
        "lodash", "three.js", "d3.js",
    ],
    "Databases": [
        "mysql", "postgresql", "sqlite", "mongodb", "redis", "cassandra",
        "oracle", "mariadb", "dynamodb", "firebase", "elasticsearch",
        "neo4j", "couchdb",
    ],
    "Cloud Skills": [
        "aws", "azure", "gcp", "google cloud", "heroku", "render",
        "vercel", "netlify", "digitalocean", "cloudflare", "lambda",
        "ec2", "s3", "kubernetes", "docker",
    ],
    "Developer Tools": [
        "git", "github", "gitlab", "bitbucket", "jenkins", "circleci",
        "travis", "jira", "postman", "swagger", "vscode", "intellij",
        "webpack", "vite", "babel", "npm", "yarn", "pnpm", "linux",
    ],
    "Soft Skills": [
        "leadership", "communication", "teamwork", "problem solving",
        "critical thinking", "adaptability", "creativity", "time management",
        "collaboration", "presentation", "negotiation", "mentoring",
    ],
}

LEARNING_RESOURCES = {
    "default": {
        "docs": "https://devdocs.io/",
        "course": "https://www.freecodecamp.org/",
        "youtube": "https://www.youtube.com/results?search_query={skill}+tutorial",
        "practice": "https://www.hackerrank.com/",
    }
}


def res_for(skill):
    s = skill.replace(" ", "+")
    return {
        "docs": f"https://www.google.com/search?q={s}+official+documentation",
        "course": f"https://www.freecodecamp.org/news/search/?query={s}",
        "youtube": f"https://www.youtube.com/results?search_query={s}+full+course",
        "practice": f"https://www.hackerrank.com/domains?q={s}",
    }


PRIORITY_MAP = {
    "Programming Languages": ("High", "20-40 hrs", "Critical", "Medium"),
    "Frameworks":            ("High", "15-30 hrs", "High",     "Medium"),
    "Libraries":             ("Medium", "8-15 hrs", "High",    "Easy"),
    "Databases":             ("High", "10-20 hrs", "Critical", "Medium"),
    "Cloud Skills":          ("High", "20-40 hrs", "Critical", "Hard"),
    "Developer Tools":       ("Medium", "5-10 hrs", "Medium",  "Easy"),
    "Soft Skills":           ("Low",  "Ongoing",   "Medium",   "Easy"),
}


# ----------------------------------------------------------------------
# Resume parsing & analysis
# ----------------------------------------------------------------------
def extract_text(file_path):
    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        try:
            reader = PdfReader(file_path)
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception:
            return ""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def extract_candidate_name(text):
    for line in text.splitlines():
        line = line.strip()
        if 2 <= len(line.split()) <= 4 and all(w[:1].isalpha() for w in line.split()):
            if not any(ch.isdigit() for ch in line) and "@" not in line:
                return line.title()
    return "Candidate"


def detect_skills(text):
    text_l = text.lower()
    found = {}
    for category, skills in SKILL_DB.items():
        matched = []
        for sk in skills:
            pattern = r"(?<![a-z0-9])" + re.escape(sk) + r"(?![a-z0-9])"
            if re.search(pattern, text_l):
                matched.append(sk)
        found[category] = sorted(set(matched))
    return found


def detect_jd_skills(jd_text):
    jd_l = jd_text.lower()
    needed = {}
    for category, skills in SKILL_DB.items():
        matched = [s for s in skills if re.search(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])", jd_l)]
        needed[category] = sorted(set(matched))
    return needed


def score_education(text):
    keywords = ["bachelor", "master", "phd", "b.tech", "m.tech", "b.sc",
                "m.sc", "mba", "degree", "university", "college", "diploma"]
    hits = sum(1 for k in keywords if k in text.lower())
    return min(100, hits * 18)


def score_experience(text):
    years = re.findall(r"(\d+)\+?\s*(?:years|yrs)", text.lower())
    yrs = max([int(y) for y in years], default=0)
    keywords = ["intern", "experience", "worked", "developed", "engineer",
                "developer", "manager", "lead", "designed", "built"]
    hits = sum(1 for k in keywords if k in text.lower())
    score = min(100, yrs * 15 + hits * 4)
    if yrs >= 5:
        level = "Senior"
    elif yrs >= 2:
        level = "Mid-level"
    elif yrs >= 1 or hits >= 3:
        level = "Junior"
    else:
        level = "Entry-level"
    return score, level, yrs


def grade(score):
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 50: return "D"
    return "F"


def recommend_roles(skills_found):
    flat = {s for arr in skills_found.values() for s in arr}
    roles = []
    front = {"react", "angular", "vue", "javascript", "typescript", "html", "css"}
    back  = {"node", "express", "django", "flask", "spring", "fastapi", "java", "python"}
    data  = {"pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "r", "matplotlib"}
    devops = {"aws", "azure", "gcp", "docker", "kubernetes", "jenkins"}
    if flat & front: roles.append("Frontend Developer")
    if flat & back: roles.append("Backend Developer")
    if (flat & front) and (flat & back): roles.append("Full Stack Developer")
    if flat & data: roles.append("Data Analyst")
    if flat & devops: roles.append("DevOps / Cloud Engineer")
    if "figma" in flat or "ui" in flat: roles.append("UI/UX Designer")
    roles.append("Software Engineer")
    seen, out = set(), []
    for r in roles:
        if r not in seen:
            seen.add(r); out.append(r)
    return out[:6]


def build_skill_gap(missing_by_cat):
    gap = []
    for cat, skills in missing_by_cat.items():
        pri, time_, impact, diff = PRIORITY_MAP.get(cat, ("Medium", "10 hrs", "Medium", "Medium"))
        for sk in skills:
            r = res_for(sk)
            gap.append({
                "skill": sk, "category": cat, "priority": pri,
                "learning_time": time_, "career_impact": impact, "difficulty": diff,
                "docs": r["docs"], "course": r["course"],
                "youtube": r["youtube"], "practice": r["practice"],
            })
    order = {"High": 0, "Medium": 1, "Low": 2}
    gap.sort(key=lambda x: order.get(x["priority"], 3))
    return gap


def improvement_plan(found, missing, jd_text):
    plan = []
    if missing:
        plan.append(f"Learn {len(missing)} missing key skill(s) prioritized by impact.")
    plan.append("Use a clean single-column resume layout — ATS parsers prefer simple structure.")
    plan.append("Mirror critical keywords from the job description in your Skills and Experience sections.")
    plan.append("Build a personal portfolio website showcasing 3–5 projects with live demos.")
    plan.append("Pin your top 6 repositories on GitHub with clear READMEs and screenshots.")
    plan.append("Optimize your LinkedIn headline and About section with target role keywords.")
    plan.append("Earn 1–2 certifications relevant to the role (e.g. AWS, Google, Meta).")
    plan.append("Quantify achievements: include metrics, percentages, and impact numbers.")
    plan.append("Build a capstone project that demonstrates an end-to-end skill set.")
    return plan


def analyze(resume_text, jd_text):
    found = detect_skills(resume_text)
    needed = detect_jd_skills(jd_text) if jd_text.strip() else {k: [] for k in SKILL_DB}

    matched_total = 0
    needed_total = 0
    missing = {}
    matched = {}
    for cat in SKILL_DB:
        need = set(needed.get(cat, []))
        have = set(found.get(cat, []))
        m = sorted(need & have)
        miss = sorted(need - have)
        matched[cat] = m
        missing[cat] = miss
        matched_total += len(m)
        needed_total += len(need)

    if needed_total > 0:
        ats_score = round((matched_total / needed_total) * 100, 1)
    else:
        ats_score = round(min(100, sum(len(v) for v in found.values()) * 3.5), 1)

    skill_score = round(min(100, sum(len(v) for v in found.values()) * 4), 1)
    edu_score = score_education(resume_text)
    exp_score, level, yrs = score_experience(resume_text)
    overall = round((ats_score * 0.4 + skill_score * 0.3 + exp_score * 0.2 + edu_score * 0.1), 1)

    name = extract_candidate_name(resume_text)
    flat_missing = []
    for arr in missing.values():
        flat_missing.extend(arr)

    return {
        "candidate": name,
        "scores": {
            "ats": ats_score, "skill": skill_score, "education": edu_score,
            "experience": exp_score, "overall": overall, "grade": grade(overall),
        },
        "experience_level": level,
        "years_experience": yrs,
        "skills_found": found,
        "skills_matched": matched,
        "skills_missing": missing,
        "skill_gap": build_skill_gap(missing),
        "improvement_plan": improvement_plan(found, flat_missing, jd_text),
        "recommended_roles": recommend_roles(found),
        "analyzed_at": datetime.utcnow().isoformat() + "Z",
    }


# ----------------------------------------------------------------------
# Routes - pages
# ----------------------------------------------------------------------
@app.route("/")
def root():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    return render_template("index.html", user=user)


@app.route("/login", methods=["GET"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/register", methods=["GET"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/health")
def api_health():
    try:
        model = load_model(MODEL_PATH)
        training_source = model.get("training_source", "unknown")
        return jsonify({"ok": True, "model_path": str(MODEL_PATH), "training_source": training_source})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ----------------------------------------------------------------------
# Routes - auth API
# ----------------------------------------------------------------------

@app.route("/auth/google")
def auth_google():
    if not GOOGLE_AUTH_ENABLED:
        return render_template(
            "oauth_missing.html",
            redirect_uri=GOOGLE_REDIRECT_URI
        )

    redirect_uri = GOOGLE_REDIRECT_URI

    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/auth/google/demo")
def auth_google_demo():
    flash("Demo authentication is disabled for security compliance. Please register or sign in via standard form.", "error")
    return redirect(url_for("login"))


@app.route("/auth/google/callback")
def auth_google_callback():
    if not GOOGLE_AUTH_ENABLED:
        flash("Google OAuth is not configured.", "error")
        return redirect(url_for("login"))
    
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        flash(f"Google authentication failed: {str(e)}", "error")
        return redirect(url_for("login"))
    
    user_payload = token.get("userinfo")
    if not user_payload:
        flash("Google authentication failed: profile information could not be retrieved.", "error")
        return redirect(url_for("login"))

    email = user_payload.get("email")
    if not email:
        flash("Google authentication failed: no email address returned.", "error")
        return redirect(url_for("login"))

    name = user_payload.get("name") or user_payload.get("given_name", "Google User")
    picture = user_payload.get("picture", "")

    user_id = create_or_update_google_user(email, name, picture)
    session.permanent = True  # Make Google login session permanent (remembered)
    set_session_user(user_id, name)
    flash("Signed in successfully with Google.", "success")
    return redirect(url_for("dashboard"))


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not name or not email or len(password) < 6:
        return jsonify({"error": "Provide a name, valid email and a password with at least 6 characters."}), 400
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"error": "Invalid email format."}), 400
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists."}), 400
    set_session_user(cur.lastrowid, name)
    return jsonify({"ok": True, "redirect": url_for("dashboard")})


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    remember = bool(data.get("remember"))
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not check_password_hash(row["password"], password):
        return jsonify({"error": "Invalid email or password."}), 401
    session.permanent = remember
    set_session_user(row["id"], row["name"])
    return jsonify({"ok": True, "redirect": url_for("dashboard")})


# ----------------------------------------------------------------------
# Routes - profile
# ----------------------------------------------------------------------
@app.route("/api/profile", methods=["GET", "POST"])
@login_required
def api_profile():
    db = get_db()
    user = current_user()
    if request.method == "GET":
        return jsonify({
            "id": user["id"], "name": user["name"], "email": user["email"],
            "avatar": user["avatar"], "created_at": user["created_at"],
        })
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or user["name"]).strip()
    email = (data.get("email") or user["email"]).strip().lower()
    try:
        db.execute("UPDATE users SET name = ?, email = ? WHERE id = ?",
                   (name, email, user["id"]))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already taken."}), 400
    return jsonify({"ok": True})


@app.route("/api/profile/password", methods=["POST"])
@login_required
def api_change_password():
    data = request.get_json(silent=True) or {}
    old = data.get("old_password") or ""
    new = data.get("new_password") or ""
    if len(new) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400
    db = get_db()
    row = db.execute("SELECT password FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if not check_password_hash(row["password"], old):
        return jsonify({"error": "Current password is incorrect."}), 400
    db.execute("UPDATE users SET password = ? WHERE id = ?",
               (generate_password_hash(new), session["user_id"]))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/profile/avatar", methods=["POST"])
@login_required
def api_avatar():
    data = request.get_json(silent=True) or {}
    avatar = data.get("avatar") or ""
    if len(avatar) > 400_000:
        return jsonify({"error": "Avatar too large."}), 400
    db = get_db()
    db.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar, session["user_id"]))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/profile/delete", methods=["POST"])
@login_required
def api_delete_account():
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (session["user_id"],))
    db.commit()
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("login")})


# ----------------------------------------------------------------------
# Routes - analyze
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# Routes - analyze
# ----------------------------------------------------------------------

@app.route("/api/analyze", methods=["POST"])
@login_required
def api_analyze():

    if "resume" not in request.files:
        return jsonify({"error": "No resume file uploaded."}), 400

    f = request.files["resume"]

    if not f or f.filename == "":
        return jsonify({"error": "Empty filename."}), 400

    if not allowed_file(f.filename):
        return jsonify({"error": "Only PDF or TXT files are supported."}), 400

    job_title = request.form.get("job_title", "").strip()
    jd_text = request.form.get("job_description", "").strip()

    filename = secure_filename(
        f"{session['user_id']}_{int(datetime.utcnow().timestamp())}_{f.filename}"
    )

    file_path = os.path.join(UPLOAD_FOLDER, filename)
    f.save(file_path)

    text = extract_text(file_path)

    if not text.strip():
        return jsonify({
            "error": "Could not extract any text from the uploaded resume."
        }), 400

    # ---------------------------
    # RecruitIQ AI Analysis
    # ---------------------------
    try:
        ai_result = ai_analyzer(text, jd_text)
    except Exception:
        ai_result = {}

    # Existing RecruitIQ Analysis
    result = analyze(text, jd_text)

    # Merge AI Results safely
    ai_payload = build_ai_payload(ai_result, result)
    result["ai_analysis"] = ai_payload
    result["ats_score"] = ai_payload.get("ats_score", result["scores"].get("ats", 0))
    result["ats"] = result["scores"].get("ats", result["ats_score"])
    result["recommendation"] = ai_payload.get("recommendation", result.get("recommended_roles", "Needs Improvement"))
    result["recommended_roles"] = result.get("recommended_roles", [])

    normalized_matched = ai_payload.get("matched_skills", {})
    normalized_missing = ai_payload.get("missing_skills", {})
    result["matched_skills"] = normalized_matched
    result["missing_skills"] = normalized_missing
    result["skills_matched"] = normalized_matched
    result["skills_missing"] = normalized_missing
    result["learning_roadmap"] = ai_payload.get("learning_roadmap") or result.get("improvement_plan", [])
    result["improvement_plan"] = result.get("improvement_plan", [])

    matched = sum(len(v) for v in normalized_matched.values()) if isinstance(normalized_matched, dict) else 0
    missing = sum(len(v) for v in normalized_missing.values()) if isinstance(normalized_missing, dict) else 0
    total = matched + missing
    result["skill_match_percentage"] = round((matched / total) * 100, 1) if total else 100
    result["scores"]["ats"] = result.get("ats_score", result["scores"].get("ats", 0))
    result["scores"]["skill"] = result["scores"].get("skill", round(result["skill_match_percentage"], 1))

    result["job_title"] = job_title
    result["filename"] = f.filename

    db = get_db()

    cur = db.execute(
        """
        INSERT INTO history
        (
            user_id,
            filename,
            job_title,
            overall_score,
            ats_score,
            skill_score,
            education_score,
            experience_score,
            data_json
        )
        VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session["user_id"],
            f.filename,
            job_title,
            result["scores"]["overall"],
            result["scores"]["ats"],
            result["scores"]["skill"],
            result["scores"]["education"],
            result["scores"]["experience"],
            json.dumps(result)
        )
    )

    db.commit()

    result["history_id"] = cur.lastrowid

    return jsonify(result)
# ----------------------------------------------------------------------
# Routes - history
# ----------------------------------------------------------------------
@app.route("/api/history", methods=["GET"])
@login_required
def api_history():
    q = (request.args.get("q") or "").strip().lower()
    order = request.args.get("order", "desc").lower()
    order_sql = "DESC" if order != "asc" else "ASC"
    db = get_db()
    rows = db.execute(
        f"""SELECT id, filename, job_title, overall_score, ats_score,
                   skill_score, experience_score, education_score, created_at
            FROM history WHERE user_id = ? ORDER BY created_at {order_sql}""",
        (session["user_id"],),
    ).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        if q and q not in item["filename"].lower() and q not in (item["job_title"] or "").lower():
            continue
        items.append(item)
    return jsonify({"items": items})


@app.route("/api/history/<int:hid>", methods=["GET", "DELETE"])
@login_required
def api_history_item(hid):
    db = get_db()
    row = db.execute(
        "SELECT * FROM history WHERE id = ? AND user_id = ?",
        (hid, session["user_id"]),
    ).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    if request.method == "DELETE":
        db.execute("DELETE FROM history WHERE id = ?", (hid,))
        db.commit()
        return jsonify({"ok": True})
    data = json.loads(row["data_json"])
    data["history_id"] = hid
    return jsonify(data)


# ----------------------------------------------------------------------
# Routes - PDF report (server-side fallback)
# ----------------------------------------------------------------------
@app.route("/api/report/<int:hid>", methods=["GET"])
@login_required
def api_report(hid):
    """
    A plain-text fallback report. The primary PDF is generated client-side
    via jsPDF (static/pdf.js) for a richer layout. This endpoint guarantees
    a server download even if the client lacks jsPDF.
    """
    db = get_db()
    row = db.execute(
        "SELECT * FROM history WHERE id = ? AND user_id = ?",
        (hid, session["user_id"]),
    ).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    data = json.loads(row["data_json"])
    buf = io.StringIO()
    buf.write("RecruitIQ — Resume Intelligence Report\n")
    buf.write("=" * 60 + "\n\n")
    buf.write(f"Candidate: {data.get('candidate') or '—'}\n")
    buf.write(f"File:      {data.get('filename') or '—'}\n")
    buf.write(f"Job:       {data.get('job_title') or '—'}\n")
    buf.write(f"Date:      {data.get('analyzed_at') or '—'}\n\n")
    s = data.get("scores", {})
    buf.write("Summary\n")
    buf.write("-------\n")
    buf.write(f"Overall:    {s.get('overall', 0)}  (Grade {s.get('grade', '—')})\n")
    buf.write(f"ATS Match:  {s.get('ats', 0)}\n")
    buf.write(f"Skills:     {s.get('skill', 0)}\n")
    buf.write(f"Experience: {s.get('experience', 0)} ({data.get('experience_level') or '—'})\n")
    buf.write(f"Education:  {s.get('education', 0)}\n\n")
    buf.write("Matched skills:\n")
    for cat, arr in data.get("skills_matched", {}).items():
        if arr:
            buf.write(f"  - {cat}: {', '.join(arr)}\n")
    buf.write("\nMissing skills:\n")
    for cat, arr in data.get("skills_missing", {}).items():
        if arr:
            buf.write(f"  - {cat}: {', '.join(arr)}\n")
    buf.write("\nImprovement plan:\n")
    for line in data.get("improvement_plan", []):
        buf.write(f"  • {line}\n")
    buf.write("\nRecommended roles:\n")
    for r in data.get("recommended_roles", []):
        buf.write(f"  • {r}\n")

    try:
        story = []
        styles = getSampleStyleSheet()
        title_style = styles["Heading1"]
        title_style.fontSize = 18
        title_style.textColor = colors.HexColor("#7c5cff")
        story.append(Paragraph("RecruitIQ Resume Intelligence Report", title_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Candidate: {data.get('candidate') or '—'}", styles["BodyText"]))
        story.append(Paragraph(f"File: {data.get('filename') or '—'}", styles["BodyText"]))
        story.append(Paragraph(f"Job: {data.get('job_title') or '—'}", styles["BodyText"]))
        story.append(Paragraph(f"Generated: {data.get('analyzed_at') or '—'}", styles["BodyText"]))
        story.append(Spacer(1, 12))

        s = data.get("scores", {})
        rows = [
            ["Overall", f"{s.get('overall', 0)} (Grade {s.get('grade', '—')})"],
            ["ATS Match", s.get("ats", 0)],
            ["Skills", s.get("skill", 0)],
            ["Experience", s.get("experience", 0)],
            ["Education", s.get("education", 0)],
        ]
        table = Table(rows, colWidths=[120, 360])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c5cff")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(Spacer(1, 12))

        def add_list(items, title):
            if not items:
                story.append(Paragraph(f"{title}: None", styles["BodyText"]))
                return
            story.append(Paragraph(title, styles["Heading3"]))
            bullet_items = [ListItem(Paragraph(item, styles["BodyText"])) for item in items]
            story.append(ListFlowable(bullet_items, bulletType="bullet"))

        add_list(data.get("recommended_roles", []), "Recommended roles")
        add_list(data.get("improvement_plan", []), "Improvement plan")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        doc.build(story)
        buffer.seek(0)
        fname = f"RecruitIQ_Report_{hid}.pdf"
        db.execute(
            "INSERT INTO reports (user_id, history_id, filename) VALUES (?, ?, ?)",
            (session["user_id"], hid, fname),
        )
        db.commit()
        return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=fname)
    except Exception:
        out = io.BytesIO(buf.getvalue().encode("utf-8"))
        fname = f"RecruitIQ_Report_{hid}.txt"
        db.execute(
            "INSERT INTO reports (user_id, history_id, filename) VALUES (?, ?, ?)",
            (session["user_id"], hid, fname),
        )
        db.commit()
        return send_file(out, mimetype="text/plain", as_attachment=True, download_name=fname)


# ----------------------------------------------------------------------
# Sample JD
# ----------------------------------------------------------------------
@app.route("/api/sample-jd")
def api_sample_jd():
    return jsonify({
        "job_title": "Full Stack Engineer",
        "job_description": (
            "We are hiring a Full Stack Engineer with strong experience in Python, "
            "JavaScript, and TypeScript. You will build features using React and Next.js "
            "on the frontend and Node.js/Express or Django on the backend. Solid "
            "knowledge of PostgreSQL, MongoDB, and Redis is required. Familiarity with "
            "AWS, Docker, Kubernetes, and CI/CD pipelines is a strong plus. We value "
            "clean code, problem solving, communication, and teamwork."
        ),
    })


# ----------------------------------------------------------------------
# Error handlers
# ----------------------------------------------------------------------
@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "File too large (max 8 MB)."}), 413


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return redirect(url_for("root"))


# ----------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Startup diagnostics
    print(f"RecruitIQ starting on port {port}")
    print(f"Google OAuth enabled: {GOOGLE_AUTH_ENABLED}")
    if not GOOGLE_AUTH_ENABLED:
        print("Google OAuth not configured. Using demo flow at /auth/google/demo")
    try:
        model = load_model(MODEL_PATH)
        print(f"Local model loaded from: {MODEL_PATH}")
    except Exception as e:
        print(f"Local model load failed: {e}")
    app.run(host="0.0.0.0", port=port, debug=False)

