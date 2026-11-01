"""Check API health, predictions and invalid input."""

import json

import joblib
import pytest
from fastapi.testclient import TestClient

from churn.api import app
from churn.model import trana_och_utvardera

CUSTOMER = {
    "alder": 35,
    "region": "Stockholm",
    "abonnemang": "Standard",
    "manader_som_kund": 12,
    "manadskostnad": 299.0,
    "data_gb_per_manad": 20.0,
    "supportarenden_12m": 2,
}

TEST_COMMIT = "a" * 40


@pytest.fixture(scope="module")
def model_folder(tmp_path_factory):
    # Create test files without changing the real outputs folder.
    folder = tmp_path_factory.mktemp("api-model")
    model, metrics = trana_och_utvardera()
    metrics["commit"] = TEST_COMMIT

    joblib.dump(model, folder / "modell.joblib")
    (folder / "matvarden.json").write_text(
        json.dumps(metrics), encoding="utf-8"
    )
    return folder


@pytest.fixture
def client(model_folder, monkeypatch):
    # Tell the API to load the temporary test model.
    monkeypatch.setenv("MODEL_DIR", str(model_folder))

    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model_sha": TEST_COMMIT,
    }


def test_predict(client):
    response = client.post("/predict", json=CUSTOMER)

    assert response.status_code == 200
    result = response.json()
    assert 0 <= result["churn_probability"] <= 1
    assert result["model_sha"] == TEST_COMMIT


def test_invalid_age_is_rejected(client):
    invalid_customer = CUSTOMER.copy()
    invalid_customer["alder"] = 17

    response = client.post("/predict", json=invalid_customer)

    assert response.status_code == 422