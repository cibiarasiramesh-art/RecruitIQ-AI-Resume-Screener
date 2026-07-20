import json
from pathlib import Path

from models.custom_resume_model import load_model, build_feature_text

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "dataset" / "train.json"


def evaluate() -> None:
    with open(DATASET_PATH, "r", encoding="utf-8") as handle:
        dataset = json.load(handle)

    model = load_model()
    predictions = []
    for item in dataset:
        text = build_feature_text(item["input"].get("resume", ""), item["input"].get("job_description", ""))
        predicted = model["score_pipeline"].predict([text])[0]
        predictions.append(float(predicted))

    avg_error = sum(abs(predictions[i] - float(item["output"].get("ats_score", 0))) for i, item in enumerate(dataset)) / max(1, len(dataset))
    print(f"Average ATS error: {avg_error:.2f}")


if __name__ == "__main__":
    evaluate()
