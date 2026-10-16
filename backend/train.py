from __future__ import annotations

from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from ml_features import answer_features, FEATURE_COLUMNS

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "answer_training.csv"
ARTIFACT_DIR = ROOT / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "answer_scorer.joblib"
METRICS_PATH = ARTIFACT_DIR / "evaluation_metrics.json"


def main() -> None:
    data = pd.read_csv(DATA_PATH).fillna("")
    required = {"question", "reference_answer", "candidate_answer", "score"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Training CSV missing columns: {sorted(missing)}")
    if len(data) < 8:
        raise ValueError("Add at least 8 labelled examples before training.")

    rows = [
        answer_features(str(row.question), str(row.reference_answer), str(row.candidate_answer))
        for row in data.itertuples(index=False)
    ]
    X = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    y = pd.to_numeric(data["score"], errors="raise").clip(0, 10)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42
    )
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("regressor", RandomForestRegressor(
            n_estimators=250, max_depth=6, min_samples_leaf=2, random_state=42
        )),
    ])
    model.fit(X_train, y_train)
    predictions = model.predict(X_test).clip(0, 10)
    metrics = {
        "dataset_rows": int(len(data)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "mae": round(float(mean_absolute_error(y_test, predictions)), 3),
        "rmse": round(float(mean_squared_error(y_test, predictions) ** 0.5), 3),
        "r2": round(float(r2_score(y_test, predictions)), 3),
        "note": "Tiny illustrative dataset: metrics are not representative of production performance.",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS, "version": "0.1.0"}, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    print("Saved:", MODEL_PATH)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
