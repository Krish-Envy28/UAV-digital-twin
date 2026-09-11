import json
from pathlib import Path
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

def train_model(data_path="data/mission_dataset.csv", model_path="ml/artifacts/mission_risk_model.json"):
    print("Loading dataset...")
    df = pd.read_csv(data_path)
    
    # Feature columns
    features = [
        "health_index", "rul_hours", "degradation_rate", "anomaly_severity", 
        "egt_deviation", "cht_deviation", "oil_pressure_deviation", 
        "vibration_deviation", "mission_duration", "mission_altitude", 
        "engine_load"
    ]
    
    X = df[features]
    y = df["label"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # ---------------------------------------------------------
    # Monotonicity Constraints
    # -1 = decreasing relationship (higher value = lower risk)
    #  1 = increasing relationship (higher value = higher risk)
    #  0 = unconstrained
    # ---------------------------------------------------------
    feature_constraints = {
        "health_index": -1,         # Higher health -> lower risk
        "rul_hours": -1,            # Higher RUL -> lower risk
        "degradation_rate": 1,      # Higher degradation -> higher risk
        "anomaly_severity": 1,      # Higher anomaly -> higher risk
        "egt_deviation": 1,         # Higher heat -> higher risk
        "cht_deviation": 1,         # Higher heat -> higher risk
        "oil_pressure_deviation": -1, # Lower pressure deviation (neg) -> higher risk (but wait, it's actual deviation. Let's leave 0 for physical devs as it depends on direction of deviation)
        "vibration_deviation": 1,
        "mission_duration": 1,      # Longer mission -> higher risk
        "mission_altitude": 1,      # Higher altitude -> higher risk
        "engine_load": 1            # Higher load -> higher risk
    }
    
    # Oil pressure is tricky because deviation can be negative. Let's unconstrain physical 
    # sensor deviations to let the model learn the exact boundary, but tightly constrain 
    # the mission params and core health metrics.
    feature_constraints["oil_pressure_deviation"] = 0
    feature_constraints["egt_deviation"] = 0
    feature_constraints["cht_deviation"] = 0
    
    monotone_tuple = tuple(feature_constraints[f] for f in features)
    
    print("Training XGBoost Classifier with monotone constraints...")
    clf = xgb.XGBClassifier(
        objective='multi:softprob',
        num_class=4,
        eval_metric='mlogloss',
        monotone_constraints=monotone_tuple,
        max_depth=4,
        n_estimators=100,
        learning_rate=0.1,
        random_state=42
    )
    
    clf.fit(X_train, y_train)
    
    # Validation
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"Validation Accuracy: {acc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # Save model
    out_path = Path(model_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clf.save_model(str(out_path))
    print(f"\nModel saved to {out_path}")
    
    # Feature Importances
    importances = clf.feature_importances_
    driver_dict = {feat: float(imp) for feat, imp in zip(features, importances)}
    
    # Save feature names and importances so the API can map them
    with open(out_path.with_suffix(".meta.json"), "w") as f:
        json.dump({"features": features, "importances": driver_dict}, f)
        
    print("Saved model metadata.")

if __name__ == "__main__":
    train_model()
