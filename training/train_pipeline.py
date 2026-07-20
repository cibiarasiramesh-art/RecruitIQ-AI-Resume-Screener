"""
Train pipeline orchestrator for RecruitIQ local model.

Steps:
- Preprocess dataset
- Train model (uses models.custom_resume_model.train_model)
- Evaluate model
- Save trained model under models/

Usage:
python training/train_pipeline.py
"""
from pathlib import Path
import argparse
import logging

from training.preprocess_data import prepare_dataset
from models.custom_resume_model import train_model, load_model
from training.evaluate_model import evaluate

logging.basicConfig(level=logging.INFO)
BASE_DIR = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true", help="Run data preparation step")
    parser.add_argument("--train", action="store_true", help="Train the model")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate the model")
    args = parser.parse_args()

    if args.prepare:
        out = prepare_dataset()
        logging.info(f"Prepared dataset at {out}")

    if args.train:
        model_path = train_model()
        logging.info(f"Trained model saved to {model_path}")

    if args.evaluate:
        evaluate()

    if not (args.prepare or args.train or args.evaluate):
        # default: run full pipeline
        out = prepare_dataset()
        logging.info(f"Prepared dataset at {out}")
        model_path = train_model()
        logging.info(f"Trained model saved to {model_path}")
        evaluate()


if __name__ == "__main__":
    main()
