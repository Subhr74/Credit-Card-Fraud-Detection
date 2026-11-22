"""Application configuration loaded from environment or defaults."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'warehouse.db'}")

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "dmdw-fraud-portal-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# Model path
MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "model.joblib"))
RESULTS_PATH = os.getenv("RESULTS_PATH", str(BASE_DIR / "results.json"))
CSV_PATH = os.getenv("CSV_PATH", str(BASE_DIR / "data" / "creditcard.csv"))

# Random Seed for Reproducibility
RANDOM_SEED = 42
