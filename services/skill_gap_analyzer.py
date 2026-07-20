import re

# -------------------------------
# RecruitIQ Skill Categories
# -------------------------------

SKILL_CATEGORIES = {

    "Programming": [
        "Python",
        "Java",
        "C",
        "C++",
        "JavaScript"
    ],

    "Frontend": [
        "HTML",
        "CSS",
        "React",
        "Angular",
        "Vue"
    ],

    "Backend": [
        "Flask",
        "Django",
        "FastAPI",
        "Node.js",
        "Express"
    ],

    "Database": [
        "MySQL",
        "SQLite",
        "MongoDB",
        "PostgreSQL"
    ],

    "Cloud": [
        "AWS",
        "Azure",
        "Docker",
        "Kubernetes"
    ],

    "AI": [
        "Machine Learning",
        "Deep Learning",
        "TensorFlow",
        "PyTorch",
        "NLP",
        "LLM",
        "LangChain"
    ],

    "Libraries": [
        "Pandas",
        "NumPy",
        "Scikit-learn"
    ],

    "Tools": [
        "Git",
        "GitHub",
        "REST API"
    ]
}


# ---------------------------------

def extract_skills(text):

    text = text.lower()

    skills = []

    for category in SKILL_CATEGORIES.values():

        for skill in category:

            pattern = r"\b" + re.escape(skill.lower()) + r"\b"

            if re.search(pattern, text):

                skills.append(skill)

    return sorted(list(set(skills)))


# ---------------------------------

def analyze_skill_gap(resume, job):

    resume_skills = extract_skills(resume)

    job_skills = extract_skills(job)

    matched = []

    missing = []

    for skill in job_skills:

        if skill in resume_skills:

            matched.append(skill)

        else:

            missing.append(skill)

    total = len(job_skills)

    if total == 0:

        percentage = 0

    else:

        percentage = round(
            (len(matched) / total) * 100,
            2
        )

    return {

        "resume_skills": resume_skills,

        "job_skills": job_skills,

        "matched_skills": matched,

        "missing_skills": missing,

        "skill_match_percentage": percentage

    }


# ---------------------------------

if __name__ == "__main__":

    resume = """

    Python

    Flask

    HTML

    CSS

    Git

    SQLite

    """

    job = """

    Python

    Flask

    Docker

    Machine Learning

    Git

    TensorFlow

    """

    from pprint import pprint

    pprint(

        analyze_skill_gap(

            resume,

            job

        )

    )