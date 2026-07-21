import json
import pickle
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline


BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "custom_resume_model.pkl"
DATASET_PATH = BASE_DIR / "dataset" / "train.json"


def clean_text(text):
    """Clean text before processing."""
    text = text or ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_feature_text(resume, job_description):
    """
    Combine resume and job description into one text input.
    """
    resume = clean_text(resume)
    job_description = clean_text(job_description)

    return f"resume: {resume} job description: {job_description}"


def train_model(dataset_path=DATASET_PATH, output_path=MODEL_PATH):
    """
    Train the ATS score prediction model.
    """

    dataset_path = Path(dataset_path)
    output_path = Path(output_path)

    with open(dataset_path, "r", encoding="utf-8") as file:
        dataset = json.load(file)

    texts = []
    scores = []

    for item in dataset:
        resume = item.get("input", {}).get("resume", "")
        job_description = item.get("input", {}).get(
            "job_description", ""
        )

        ats_score = item.get("output", {}).get(
            "ats_score", 0
        )

        feature_text = build_feature_text(
            resume,
            job_description
        )

        texts.append(feature_text)
        scores.append(float(ats_score))

    if not texts:
        raise ValueError("Training dataset is empty.")

    model_pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                min_df=1
            )
        ),
        (
            "regressor",
            Ridge(alpha=1.0)
        )
    ])

    model_pipeline.fit(texts, scores)

    model_data = {
        "score_pipeline": model_pipeline
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(output_path, "wb") as file:
        pickle.dump(model_data, file)

    return output_path


def load_model(model_path=MODEL_PATH):
    """
    Load the trained ATS model.
    """

    model_path = Path(model_path)

    if not model_path.exists():
        print("Model not found.")
        print("Training a new model...")

        train_model(
            dataset_path=DATASET_PATH,
            output_path=model_path
        )

    with open(model_path, "rb") as file:
        model = pickle.load(file)

    return model


def predict_resume_match(
    resume_text,
    job_description
):
    """
    Predict ATS score for a resume against a job description.
    """

    model = load_model()

    feature_text = build_feature_text(
        resume_text,
        job_description
    )

    predicted_score = model[
        "score_pipeline"
    ].predict([feature_text])[0]

    # Keep score between 0 and 100
    predicted_score = max(
        0,
        min(100, float(predicted_score))
    )

    return round(predicted_score, 2)


if __name__ == "__main__":

    print("Training custom resume model...")

    model_path = train_model()

    print(
        f"Model trained successfully: {model_path}"
    )

    test_score = predict_resume_match(
        "Java, MySQL, HTML, CSS",
        "Backend Developer requiring Java, Spring Boot, REST APIs"
    )

    print(
        f"Test ATS Score: {test_score}"
    )