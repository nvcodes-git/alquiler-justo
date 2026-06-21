"""
Hedonic OLS pricing model for Lima rental apartments.

Model spec (log-linear):
    ln(price_pen) = β0 + β1·ln(area_m2) + β2·bedrooms + β3·bathrooms
                  + β4·floor + Σγ_d·distrito_d + Σδ_a·amenity_a + ε

Trained on Infocasas listings (Miraflores, San Isidro, Surco, Magdalena).
Robust standard errors (HC1).
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm

logger = logging.getLogger(__name__)

DB_PATH = Path("data/raw/listings.db")
MIN_OBS_PER_DISTRICT = 20
AMENITY_COLS = ["piscina", "gimnasio", "cochera", "ascensor", "seguridad",
                "terraza", "amoblado", "aire"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(db_path: Path = DB_PATH) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("""
        SELECT district, price_pen, area_m2, bedrooms, bathrooms,
               floor, antiquity_years, amenities_raw
        FROM listings
        WHERE price_pen IS NOT NULL
          AND price_pen > 300
          AND area_m2   IS NOT NULL
          AND area_m2   > 15
          AND area_m2   < 600
          AND bedrooms  IS NOT NULL
    """, conn)
    conn.close()

    # Parse amenities JSON
    def parse_amenities(raw):
        try:
            return json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    amenities = df["amenities_raw"].apply(parse_amenities).apply(pd.Series)
    for col in AMENITY_COLS:
        df[col] = amenities.get(col, 0).fillna(0).astype(int)

    df = df.drop(columns=["amenities_raw"])
    df["floor"] = df["floor"].fillna(0).clip(0, 30)
    df["bathrooms"] = df["bathrooms"].fillna(1).clip(1, 6)

    # Drop price outliers (>3σ on log scale)
    df["log_price"] = np.log(df["price_pen"])
    mean_lp = df["log_price"].mean()
    std_lp  = df["log_price"].std()
    df = df[(df["log_price"] > mean_lp - 3 * std_lp) &
            (df["log_price"] < mean_lp + 3 * std_lp)]

    # Drop area outliers similarly
    df["log_area"] = np.log(df["area_m2"])
    mean_la = df["log_area"].mean()
    std_la  = df["log_area"].std()
    df = df[(df["log_area"] > mean_la - 3 * std_la) &
            (df["log_area"] < mean_la + 3 * std_la)]

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Model fitting
# ---------------------------------------------------------------------------

@dataclass
class ModelResults:
    params: pd.Series
    rsquared: float
    rsquared_adj: float
    rmse_pct: float        # RMSE as % of mean price (intuitive for pitch)
    n_obs: int
    districts: list[str]
    feature_cols: list[str]

    def summary_str(self) -> str:
        return (
            f"R²={self.rsquared:.3f}  adj-R²={self.rsquared_adj:.3f}  "
            f"RMSE≈{self.rmse_pct:.1f}%  n={self.n_obs}"
        )


def build_features(df: pd.DataFrame, districts: list[str]) -> pd.DataFrame:
    """Construct the design matrix X from a DataFrame."""
    X = pd.DataFrame(index=df.index)
    X["const"]     = 1.0          # explicit — sm.add_constant skips on 1-row DFs
    X["log_area"]  = np.log(df["area_m2"].clip(lower=1))
    X["bedrooms"]  = df["bedrooms"].clip(0, 6).astype(float)
    X["bathrooms"] = df["bathrooms"].clip(1, 6).astype(float)
    X["floor"]     = df["floor"].clip(0, 30).astype(float)

    # District dummies (drop first = miraflores as reference)
    for d in districts[1:]:
        X[f"dist_{d}"] = (df["district"] == d).astype(float)

    # Amenity dummies
    for col in AMENITY_COLS:
        if col in df.columns:
            X[col] = df[col].fillna(0).astype(float)

    return X


def fit_model(db_path: Path = DB_PATH) -> tuple["OLSModel", ModelResults]:
    df = load_data(db_path)

    # Keep only districts with enough observations
    dist_counts = df["district"].value_counts()
    valid_districts = sorted(dist_counts[dist_counts >= MIN_OBS_PER_DISTRICT].index.tolist())
    df = df[df["district"].isin(valid_districts)].copy()

    X = build_features(df, valid_districts)
    y = df["log_price"]

    ols = sm.OLS(y, X).fit(cov_type="HC1")

    y_pred = ols.predict(X)
    residuals_pct = np.exp(y - y_pred) - 1          # multiplicative residual
    rmse_pct = np.sqrt(np.mean(residuals_pct ** 2)) * 100

    results = ModelResults(
        params=ols.params,
        rsquared=ols.rsquared,
        rsquared_adj=ols.rsquared_adj,
        rmse_pct=rmse_pct,
        n_obs=len(df),
        districts=valid_districts,
        feature_cols=list(X.columns),
    )

    model = OLSModel(ols_result=ols, districts=valid_districts, df_train=df)
    logger.info(f"Model fitted: {results.summary_str()}")
    return model, results


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

@dataclass
class Prediction:
    fair_price_pen: float
    deviation_pct: float        # (listed - fair) / fair * 100
    percentile: float           # % of comparable listings cheaper than this
    verdict: str                # "buen_precio" | "justo" | "sobrevalorado"
    verdict_emoji: str
    n_comparables: int


class OLSModel:
    def __init__(self, ols_result, districts: list[str], df_train: pd.DataFrame):
        self._ols   = ols_result
        self.districts = districts
        self._df    = df_train

    def predict(
        self,
        area_m2: float,
        bedrooms: int,
        bathrooms: int,
        district: str,
        floor: int = 1,
        amenities: Optional[dict] = None,
        listed_price_pen: Optional[float] = None,
    ) -> Prediction:
        amenities = amenities or {}

        row = {
            "area_m2":   area_m2,
            "bedrooms":  bedrooms,
            "bathrooms": bathrooms,
            "floor":     floor,
            "district":  district if district in self.districts else self.districts[0],
        }
        for col in AMENITY_COLS:
            row[col] = int(amenities.get(col, 0))

        row_df = pd.DataFrame([row])
        X_row  = build_features(row_df, self.districts)

        # Align columns in case of mismatch
        X_row  = X_row.reindex(columns=self._ols.params.index, fill_value=0)

        log_pred   = self._ols.predict(X_row)[0]
        fair_price = float(np.exp(log_pred))

        # Percentile vs comparables in same district with similar area (±25%) and bedrooms
        comps = self._df[
            (self._df["district"] == row["district"]) &
            (self._df["area_m2"].between(area_m2 * 0.75, area_m2 * 1.25)) &
            (self._df["bedrooms"] == bedrooms)
        ]["price_pen"]

        if listed_price_pen and len(comps) >= 3:
            percentile = float((comps < listed_price_pen).mean() * 100)
            n_comps    = len(comps)
        elif listed_price_pen:
            # Fallback: all same district
            comps_all  = self._df[self._df["district"] == row["district"]]["price_pen"]
            percentile = float((comps_all < listed_price_pen).mean() * 100)
            n_comps    = len(comps_all)
        else:
            percentile = 50.0
            n_comps    = 0

        # Verdict
        if listed_price_pen:
            deviation_pct = (listed_price_pen - fair_price) / fair_price * 100
        else:
            deviation_pct = 0.0

        if deviation_pct < -10 or percentile < 25:
            verdict, emoji = "buen_precio", "🟢"
        elif deviation_pct > 10 or percentile > 75:
            verdict, emoji = "sobrevalorado", "🔴"
        else:
            verdict, emoji = "justo", "🟡"

        return Prediction(
            fair_price_pen=round(fair_price, 0),
            deviation_pct=round(deviation_pct, 1),
            percentile=round(percentile, 1),
            verdict=verdict,
            verdict_emoji=emoji,
            n_comparables=n_comps,
        )


# ---------------------------------------------------------------------------
# Singleton loader (cache model in memory for Streamlit)
# ---------------------------------------------------------------------------

_cached_model: Optional[tuple["OLSModel", ModelResults]] = None


def get_model(db_path: Path = DB_PATH) -> tuple["OLSModel", ModelResults]:
    global _cached_model
    if _cached_model is None:
        _cached_model = fit_model(db_path)
    return _cached_model
