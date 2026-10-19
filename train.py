"""Train EcoSense on historical data and save the artifacts for the backend."""
import logging
import sys

import pandas as pd

from ecosense import fit, save_artifacts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DATA_PATH = sys.argv[1] if len(sys.argv) > 1 else "factory_data.csv"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "artifacts.joblib"

if __name__ == "__main__":
    try:
        raw = pd.read_csv(DATA_PATH)
        save_artifacts(fit(raw), OUT_PATH)
    except (FileNotFoundError, ValueError, pd.errors.ParserError) as exc:
        logging.error("Training failed: %s", exc)
        sys.exit(1)
