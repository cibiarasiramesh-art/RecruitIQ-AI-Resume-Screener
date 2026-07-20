# RecruitIQ Training Guide

This repository ships a minimal training pipeline to build the local resume model used for ATS scoring and missing-skill prediction.

Prerequisites
- Create and activate a virtualenv
- Install dependencies in `requirements.txt`:

```bash
python -m venv venv
# Windows
venv\Scripts\activate
pip install -r requirements.txt
# if you need to download a sentence-transformers model in advance:
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
# If using spaCy language model:
python -m spacy download en_core_web_sm
```

Run full pipeline

```bash
python training/train_pipeline.py
```

Run individual steps

```bash
python training/train_pipeline.py --prepare
python training/train_pipeline.py --train
python training/train_pipeline.py --evaluate
```

Notes
- The pipeline uses local data found in `dataset/train.json` and saves the trained model to `models/custom_resume_model.joblib`.
- All inference is performed locally; no external AI APIs are used.
