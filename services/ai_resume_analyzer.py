# Standard and ML imports
import os
import re
import math
import logging
from models.custom_resume_model import predict_resume_match

try:
    import spacy
except Exception:
    spacy = None

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    SentenceTransformer = None
    cosine_similarity = None

logging.basicConfig(level=logging.INFO)


def _load_spacy():
    if not spacy:
        return None
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        try:
            return spacy.blank("en")
        except Exception:
            return None


_NLP = _load_spacy()


def _clean_with_spacy(text: str) -> str:
    if not _NLP:
        return (text or "").lower()
    doc = _NLP(text or "")
    tokens = [t.lemma_.lower() for t in doc if not (t.is_stop or t.is_punct or t.is_space)]
    return " ".join(tokens)


_ST_MODEL = None
def _load_st_model(name: str = "all-MiniLM-L6-v2"):
    global _ST_MODEL
    if _ST_MODEL is not None:
        return _ST_MODEL
    # Load only from a local directory to enforce offline mode.
    if not SentenceTransformer:
        logging.warning("SentenceTransformer not installed; semantic matching disabled.")
        return None
    local_dir = os.environ.get("SENTENCE_TRANSFORMER_LOCAL_DIR", os.path.join("models", "sentence_transformer"))
    # If an explicit local path is provided and exists, load from there. Do NOT attempt network download.
    if os.path.isdir(local_dir):
        try:
            logging.info(f"Loading Sentence-Transformer model from local path: {local_dir}")
            _ST_MODEL = SentenceTransformer(local_dir)
            return _ST_MODEL
        except Exception as e:
            logging.warning(f"Failed to load local Sentence-Transformer from {local_dir}: {e}")
            _ST_MODEL = None
            return None
    else:
        logging.warning(
            f"Sentence-Transformer local model not found at '{local_dir}'.\n"
            "Embedding-based semantic matching will be disabled.\n"
            "To enable, download the model once using scripts/setup_sentence_transformer.py"
        )
        return None
    return _ST_MODEL


# ------------------------------------
# Extract Skills from Text
# ------------------------------------

SKILLS = [
    "Python",
    "Java",
    "C",
    "C++",
    "Flask",
    "Django",
    "FastAPI",
    "HTML",
    "CSS",
    "JavaScript",
    "React",
    "Angular",
    "Vue",
    "Node.js",
    "Express",
    "MySQL",
    "SQLite",
    "PostgreSQL",
    "MongoDB",
    "Git",
    "GitHub",
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "REST API",
    "TensorFlow",
    "PyTorch",
    "Machine Learning",
    "Deep Learning",
    "NLP",
    "LLM",
    "LangChain",
    "Pandas",
    "NumPy",
    "Scikit-learn"
]


def extract_skills(text):

    found = []

    text = text.lower()

    for skill in SKILLS:

        pattern = r"\b" + re.escape(skill.lower()) + r"\b"

        if re.search(pattern, text):
            found.append(skill)

    return sorted(list(set(found)))


# ------------------------------------
# Skill Gap
# ------------------------------------

def skill_gap(resume_text, job_description):

    resume_skills = extract_skills(resume_text)

    job_skills = extract_skills(job_description)

    matched = []

    missing = []

    for skill in job_skills:

        if skill in resume_skills:
            matched.append(skill)

        else:
            missing.append(skill)

    return matched, missing


# ------------------------------------
# Learning Roadmap
# ------------------------------------

def learning_roadmap(missing):

    roadmap = []

    for skill in missing:

        roadmap.append(f"Learn {skill}")

    return roadmap


# ------------------------------------
# AI Resume Analysis
# ------------------------------------

def analyze_resume(resume_text, job_description):
    # Preprocess using spaCy (lemmatize, remove stopwords) when available
    resume_clean = _clean_with_spacy(resume_text)
    jd_clean = _clean_with_spacy(job_description)

    # Model-based prediction (scikit-learn pipeline)
    model_result = predict_resume_match(resume_text, job_description)

    # Simple skill gap detection based on keyword matcher
    matched, missing = skill_gap(resume_text, job_description)

    # Embedding similarity (sentence-transformers) as an auxiliary ATS signal
    embed_score = None
    st = _load_st_model()
    if st and cosine_similarity:
        try:
            rvec = st.encode(resume_clean)
            jvec = st.encode(jd_clean)
            sim = cosine_similarity([rvec], [jvec])[0][0]
            embed_score = round(float(sim) * 100, 1)
        except Exception:
            embed_score = None

    model_ats = model_result.get("ats_score", 0)
    if embed_score is not None:
        # blend model prediction with embedding similarity (70/30)
        ats_score = round((model_ats * 0.7 + embed_score * 0.3), 1)
    else:
        ats_score = model_ats

    if ats_score >= 85:
        recommendation = "Excellent Match"
    elif ats_score >= 70:
        recommendation = "Good Match"
    elif ats_score >= 50:
        recommendation = "Average Match"
    else:
        recommendation = model_result.get("recommendation", "Needs Improvement")

    missing_skills = model_result.get("missing_skills", missing)
    roadmap = model_result.get("learning_roadmap", learning_roadmap(missing_skills))

    return {
        "ats_score": ats_score,
        "matched_skills": matched,
        "missing_skills": missing_skills,
        "recommendation": recommendation,
        "learning_roadmap": roadmap,
        "embedding_similarity": embed_score,
    }


# ------------------------------------
# Testing
# ------------------------------------

if __name__ == "__main__":

    resume = """
    Python
    Flask
    MySQL
    Git
    HTML
    CSS
    """

    job = """
    Python
    Flask
    Docker
    Machine Learning
    TensorFlow
    Git
    """

    result = analyze_resume(
        resume,
        job
    )

    from pprint import pprint

    pprint(result)