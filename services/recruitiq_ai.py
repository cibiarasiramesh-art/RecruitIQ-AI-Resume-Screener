from services.ai_resume_analyzer import analyze_resume
from services.skill_gap_analyzer import analyze_skill_gap
from services.roadmap_generator import generate_learning_roadmap


def analyze(resume_text, job_description):

    ai_result = analyze_resume(
        resume_text,
        job_description
    )

    skill_result = analyze_skill_gap(
        resume_text,
        job_description
    )

    roadmap = generate_learning_roadmap(
        skill_result["missing_skills"]
    )

    return {

        "ats_score":
            ai_result["ats_score"],

        "recommendation":
            ai_result["recommendation"],

        "matched_skills":
            skill_result["matched_skills"],

        "missing_skills":
            skill_result["missing_skills"],

        "skill_match_percentage":
            skill_result["skill_match_percentage"],

        "learning_roadmap":
            roadmap

    }


if __name__ == "__main__":

    resume = """
    Python
    Flask
    SQLite
    Git
    HTML
    CSS
    """

    job = """
    Backend Developer

    Required Skills

    Python
    Flask
    Docker
    TensorFlow
    Machine Learning
    Git
    """

    from pprint import pprint

    pprint(

        analyze(

            resume,

            job

        )

    )