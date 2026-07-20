import json
import re
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "dataset" / "train.json"
PREPARED_PATH = BASE_DIR / "dataset" / "prepared.json"


def clean_text(text: str) -> str:
    text = text or ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def prepare_dataset(path: Path = DATASET_PATH, output_path: Path = PREPARED_PATH) -> Path:
    with open(path, "r", encoding="utf-8") as handle:
        raw_items = json.load(handle)

    prepared = []
    for item in raw_items:
        resume = clean_text(item.get("input", {}).get("resume", ""))
        job = clean_text(item.get("input", {}).get("job_description", ""))
        output = item.get("output", {})
        prepared.append({
            "resume": resume,
            "job_description": job,
            "ats_score": float(output.get("ats_score", 0)),
            "missing_skills": output.get("missing_skills", []),
            "recommendation": output.get("recommendation", "Needs Improvement"),
            "learning_roadmap": output.get("learning_roadmap", []),
        })

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(prepared, handle, indent=2)

    return output_path


if __name__ == "__main__":
    print(prepare_dataset())
