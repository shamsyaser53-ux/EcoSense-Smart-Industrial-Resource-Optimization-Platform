# AGENTS.md — EcoSense

## Architecture & Subsystems

- **Unified SaaS & ML Backend (`main.py`)**: Primary production entrypoint.
  - Entry: `uvicorn main:app --reload` (port 8000).
  - Integrates Auth (`routers/auth.py`), What-If Simulation (`routers/simulation.py`), Rule Waste (`routers/waste.py`), and ML Engine (`routers/ml.py` + `services/ml_service.py`).
  - Unified `/analyze`: Dispatches to ML anomaly detection when `records` is provided; dispatches to aggregate cost calculation when resource consumption numbers (`electricity_kwh`, etc.) are provided.
  - DB: SQLAlchemy models in `models.py` (`Company`, `ConsumptionRecord`, `AnalysisResult`, `SimulationResult`) and `auth_models.py` (`User`).
  - CORS: Configured via `CORS_ORIGINS` in `.env` (handled by `CORSMiddleware`).

- **Standalone ML Microservice (`app.py`)**: Lightweight stateless service.
  - Entry: `uvicorn app:app --reload`.
  - Re-uses `services/ml_service.py` under the hood. Contract documented in `API_CONTRACT.md`.
  - Artifacts: `artifacts.joblib` is version-locked to scikit-learn. Retrain: `python train.py factory_data.csv artifacts.joblib`.
  - Catalog: `solutions_catalog.csv` edits apply immediately without retraining.
  - Metric distinction: `waste_found_egp` (detected anomaly excess) != `annual_saving_egp` (catalog `saving_pct` * annualized consumption).

- **Frontend (`frontend/`)**: Static client with API connector.
  - Entry: `index.html` + `app.js` + `style.css` (React 18 + Chart.js via CDN).
  - API Client: `frontend/api.js` provides client methods (`EcoSenseAPI`) to talk to `main.py` (`http://127.0.0.1:8000`).
  - Run via static file server (e.g. `npx serve frontend` or VS Code Live Server), not uvicorn.

## Environment & Commands

- **Python Runtime**: Use Python 3.11 (`uv venv --python 3.11 .venv && uv pip install -r requirements.txt`).
- **Configuration**: Copy `.env.example` to `.env` (contains `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`).
- **Running Pytest**: Always run as a module: `python -m pytest` (or `.\.venv\Scripts\python.exe -m pytest`).
  - Running bare `pytest` on Windows fails with `ModuleNotFoundError: No module named 'database'`.
- **Run Single Test**: `python -m pytest tests/test_auth.py -k test_register_company -v`
- **ML Sanity Check**: `python test_ecosense.py` (prints precision/recall/F1; requires `artifacts.joblib` and CSVs).
- **Project Full Audit**: `python audit_project.py` (runs syntax, test suite, route extraction -> `ecosense_audit_report.txt`).

## Operational Gotchas & Quirks

- **Persistent Secret Key**: `security.py` reads `SECRET_KEY` from `.env`. If unset, it generates an ephemeral key that invalidates all user tokens on server reload. Keep `SECRET_KEY` set in `.env`.
- **Password Limit**: Bcrypt hard-limits passwords to 72 bytes. `schemas_auth.py` validates UTF-8 byte length (returning 422 if exceeded) before hashing.
- **Price Validation**: Custom validator `services/ml_service.validate_prices` rejects non-numeric or boolean values (`True`/`False`) to prevent type coercion.
- **CSV Upload Limit**: `POST /analyze-csv` enforces a 15MB maximum file size to prevent memory exhaustion (DoS).
- **SQLite Concurrency & Migrations**: `database.py` executes an in-place migration for `period_type` on startup (`lifespan`). Existing `ecosense*.db` files in repo root are dev artifacts. Tests override DB with in-memory SQLite (`sqlite://` via `tests/conftest.py`).
- **File Encoding**: Do NOT save python test files with UTF-8 BOM (`\xef\xbb\xbf`), as Python syntax checkers fail with `SyntaxError: invalid non-printable character U+FEFF`.
