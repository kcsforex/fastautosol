
# 2026.04.10  10.00
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error,  accuracy_score, precision_score, recall_score, f1_score

# ---- Clean + feature engineering ----
def prepare(df: pd.DataFrame) -> pd.DataFrame:
    
    d = df.copy()
    d = d.replace({"null": np.nan})
    d["dep_sched"] = pd.to_datetime(d["departure_scheduled_ts"].astype(str), errors="coerce")
    d["dep_actual"] = pd.to_datetime(d["departure_actual_ts"].astype(str), errors="coerce")
    d["arr_sched"] = pd.to_datetime(d["arrival_scheduled_ts"].astype(str), errors="coerce")
    d["arr_actual"] = pd.to_datetime(d["arrival_actual_ts"].astype(str), errors="coerce")

    d["arrival_delay"] = (d["arr_actual"] - d["arr_sched"]).dt.total_seconds() / 60
    d["dep_delay"]     = (d["dep_actual"] - d["dep_sched"]).dt.total_seconds() / 60
    d["dep_hour"] = d["dep_sched"].dt.hour
    d["dep_dow"]  = d["dep_sched"].dt.dayofweek
    d["is_delayed"] = (d["arrival_delay"] >= 15).astype("Int64")  # allow NA

    return d

# ========= Regression (arrival_delay minutes) =========
def reg_metrics(y_test, y_pred):
    metrics = { "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
                "mae":  float(mean_absolute_error(y_test, y_pred)),
                "r2":   float(r2_score(y_test, y_pred)) }   
    return metrics

def train_linear(df):
    df = df.dropna(subset=["arrival_delay"]).copy()
    X = df[["dep_delay", "dep_hour", "dep_dow"]].fillna(0)
    y = df["arrival_delay"].astype(float)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), ("regressor", LinearRegression())]).fit(X_tr, y_tr)
    return model, reg_metrics(y_te, model.predict(X_te))

def train_tree_linear(df, max_depth=None, random_state=42):
    d = df.dropna(subset=["arrival_delay"]).copy()
    X = d[["dep_delay", "dep_hour", "dep_dow"]].fillna(0)
    y = d["arrival_delay"].astype(float)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), \
    ("regressor", DecisionTreeRegressor(max_depth=max_depth, random_state=random_state))]).fit(X_tr, y_tr)
    return model, reg_metrics(y_te, model.predict(X_te))

def train_rf_linear(df, n_estimators=300, max_depth=None, random_state=42):
    d = df.dropna(subset=["arrival_delay"]).copy()
    X = d[["dep_delay", "dep_hour", "dep_dow"]].fillna(0)
    y = d["arrival_delay"].astype(float)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), \
    ("regressor", RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth, random_state=random_state))]).fit(X_tr, y_tr)
    return model, reg_metrics(y_te, model.predict(X_te))

def train_gbm_linear(df, n_estimators=300, learning_rate=0.06, max_depth=3, random_state=42, subsample=1.0):
    d = df.dropna(subset=["arrival_delay"]).copy()
    X = d[["dep_delay", "dep_hour", "dep_dow"]].fillna(0)
    y = d["arrival_delay"].astype(float)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=random_state)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), \
    ("regressor", GradientBoostingRegressor(n_estimators=n_estimators, learning_rate=learning_rate, max_depth=max_depth, subsample=subsample, random_state=random_state))]).fit(X_tr, y_tr)
    return model, reg_metrics(y_te, model.predict(X_te))

def train_hgb_linear(df, learning_rate=0.06, max_depth=None, max_iter=300, random_state=42):
    d = df.dropna(subset=["arrival_delay"]).copy()
    X = d[["dep_delay", "dep_hour", "dep_dow"]].fillna(0)
    y = d["arrival_delay"].astype(float)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=random_state)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), \
    ("regressor", HistGradientBoostingRegressor(learning_rate=learning_rate, max_depth=max_depth, max_iter=max_iter, random_state=random_state))]).fit(X_tr, y_tr)
    return model, reg_metrics(y_te, model.predict(X_te))

# ========= Classification (is_delayed >= 15 min) =========
def clf_metrics(y_test, y_pred):
    metrics = { "acc":  float(accuracy_score(y_test, y_pred)),
                "prec": float(precision_score(y_test, y_pred, zero_division=0)),
                "rec":  float(recall_score(y_test, y_pred, zero_division=0)),
                "f1":   float(f1_score(y_test, y_pred, zero_division=0)) }
    return metrics

def train_logistic(df):
    d = df.dropna(subset=["is_delayed"]).copy()
    X = d[["dep_delay", "dep_hour", "dep_dow"]].fillna(0)
    y = d["is_delayed"].astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), \
    ("classifier",  LogisticRegression(max_iter=200, class_weight="balanced"))]).fit(X_tr, y_tr)
    return model, clf_metrics(y_te, model.predict(X_te))

def train_tree_logistic(df, max_depth=None, random_state=42):
    d = df.dropna(subset=["is_delayed"]).copy()
    X = d[["dep_delay", "dep_hour", "dep_dow"]].fillna(0)
    y = d["is_delayed"].astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), \
    ("classifier",  DecisionTreeClassifier(max_depth=max_depth, random_state=random_state))]).fit(X_tr, y_tr)
    return model, clf_metrics(y_te, model.predict(X_te))

def train_rf_logistic(df, n_estimators=300, max_depth=None, random_state=42):
    d = df.dropna(subset=["is_delayed"]).copy()
    X = d[["dep_delay", "dep_hour", "dep_dow"]].fillna(0)
    y = d["is_delayed"].astype(int) 
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), \
    ("classifier",  RandomForestClassifier(n_estimators=n_estimators,max_depth=max_depth,random_state=random_state,class_weight="balanced"))]).fit(X_tr, y_tr)
    return model, clf_metrics(y_te, model.predict(X_te))

def train_gbm_logistic(df, n_estimators=300, learning_rate=0.06, max_depth=3, random_state=42, subsample=1.0):
    d = df.dropna(subset=["is_delayed"]).copy()  
    X = d[["dep_delay", "dep_hour", "dep_dow"]].fillna(0)
    y = d["is_delayed"].astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=random_state, stratify=y)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), \
    ("classifier",  GradientBoostingClassifier(n_estimators=n_estimators, learning_rate=learning_rate,max_depth=max_depth, subsample=subsample, random_state=random_state))]).fit(X_tr, y_tr)
    return model, clf_metrics(y_te, model.predict(X_te))

def train_hgb_logistic(df, learning_rate=0.06, max_depth=None, max_iter=300, random_state=42):
    d = df.dropna(subset=["is_delayed"]).copy()
    X = d[["dep_delay", "dep_hour", "dep_dow"]].fillna(0)
    y = d["is_delayed"].astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=random_state, stratify=y)
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), \
    ("classifier",  HistGradientBoostingClassifier(learning_rate=learning_rate, max_depth=max_depth, max_iter=max_iter, random_state=random_state))]).fit(X_tr, y_tr)
    return model, clf_metrics(y_te, model.predict(X_te))

# ======================================================
#  Predictions
# ======================================================

def predict_latest_linear(model, df: pd.DataFrame, n=12):
    latest = df.sort_values("dep_sched", ascending=False).head(n).copy()
    X = latest[["dep_delay", "dep_hour", "dep_dow"]]
    latest["pred_delay"] = model.predict(X)

    cols = ["route_key", "dep_sched", "arrival_delay", "pred_delay"]
    return latest[[c for c in cols if c in latest.columns]]

def predict_latest_logistic(model, df: pd.DataFrame, n=12):
    latest = df.sort_values("dep_sched", ascending=False).head(n).copy()
    X = latest[["dep_delay", "dep_hour", "dep_dow"]]

    proba = model.predict_proba(X)[:, 1]
    latest["pred_prob_delay"] = proba
    latest["pred_flag_delay"] = (proba >= 0.5).astype(int)

    cols = ["route_key", "dep_sched", "pred_prob_delay", "pred_flag_delay"]
    return latest[[c for c in cols if c in latest.columns]]






