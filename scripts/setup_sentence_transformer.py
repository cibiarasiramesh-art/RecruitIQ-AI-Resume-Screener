"""
Download and save the Sentence-Transformers model locally for offline use.
This script downloads the model 'all-MiniLM-L6-v2' and saves it under
models/sentence_transformer/ so the application can load it offline.

Usage (one-time, while online):
    python scripts/setup_sentence_transformer.py

Optional environment variables:
    SENTENCE_TRANSFORMER_MODEL  - model name to download (default: all-MiniLM-L6-v2)
    SENTENCE_TRANSFORMER_LOCAL_DIR - local path to save the model (default: models/sentence_transformer)

Notes:
- This will perform a network download. Do this only once on a machine with internet access.
- Do NOT commit the downloaded weights into source control. Add the models/ directory to .gitignore.
"""
import os
import sys

model_name = os.environ.get("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
local_dir = os.environ.get("SENTENCE_TRANSFORMER_LOCAL_DIR", os.path.join("models", "sentence_transformer"))

try:
    from sentence_transformers import SentenceTransformer
except Exception as e:
    print("Error: sentence-transformers is not installed. Install with: pip install sentence-transformers")
    sys.exit(1)

os.makedirs(local_dir, exist_ok=True)
print(f"Downloading Sentence-Transformers model '{model_name}' and saving to: {local_dir}")
try:
    model = SentenceTransformer(model_name)
    model.save(local_dir)
    print("Model saved successfully.")
    print("You can now run the app offline; the analyzer will load the local model from:", local_dir)
except Exception as e:
    print("Failed to download or save the model:", e)
    sys.exit(2)
