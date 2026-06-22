"""Tests del modelo hedónico OLS."""
from pathlib import Path

import pytest

from backend.app.model import fit_model, Prediction

DB = Path("data/listings.db")


@pytest.fixture(scope="module")
def fitted():
    return fit_model(DB)


def test_model_fits_with_reasonable_quality(fitted):
    _model, results = fitted
    assert results.n_obs > 500, "muy pocas observaciones"
    assert 0.5 < results.rsquared <= 1.0, f"R² fuera de rango: {results.rsquared}"
    assert results.rmse_pct > 0


def test_all_eleven_districts_present(fitted):
    _model, results = fitted
    assert len(results.districts) == 11


def test_prediction_is_sensible(fitted):
    model, _results = fitted
    pred = model.predict(
        area_m2=80, bedrooms=2, bathrooms=2, district="miraflores",
        floor=4, amenities={"cochera": 1}, listed_price_pen=3000,
    )
    assert isinstance(pred, Prediction)
    assert 800 < pred.fair_price_pen < 30000
    assert pred.fair_price_low <= pred.fair_price_pen <= pred.fair_price_high
    assert pred.verdict in {"buen_precio", "justo", "sobrevalorado"}


def test_decomposition_sums_to_fair_price(fitted):
    model, _results = fitted
    pred = model.predict(
        area_m2=90, bedrooms=3, bathrooms=2, district="san-isidro",
        floor=5, amenities={"ascensor": 1, "vista_mar": 1},
    )
    total = sum(pred.contributions.values())
    assert abs(total - pred.fair_price_pen) < 5, "el desglose no suma al precio justo"


def test_sea_view_increases_price(fitted):
    model, _results = fitted
    base = model.predict(area_m2=90, bedrooms=2, bathrooms=2,
                         district="barranco", floor=5, amenities={})
    sea = model.predict(area_m2=90, bedrooms=2, bathrooms=2,
                        district="barranco", floor=5, amenities={"vista_mar": 1})
    assert sea.fair_price_pen > base.fair_price_pen
