"""HTTP service for the churn model."""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

from churn.data import FEATURES, skapa_features

state = {}

class Customer(BaseModel):
    alder: int = Field(ge=18, le=100)
    region: str
    abonnemang: str
    manader_som_kund: int = Field(ge=0)
    manadskostnad: float = Field(gt=0)
    data_gb_per_manad: float = Field(ge=0)
    supportarenden_12m: int = Field(ge=0)


class Prediction(BaseModel):
    churn_probability: float = Field(ge=0, le=1)
    model_sha: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    model_dir = Path(os.environ.get("MODEL_DIR", "outputs"))

    # Load the model and its metadata once, before accepting requests.
    state["model"] = joblib.load(model_dir / "modell.joblib")
    state["metadata"] = json.loads(
        (model_dir / "matvarden.json").read_text(encoding="utf-8")
    )
    # Startup is complete: let FastAPI handle requests.
    yield

    # Release the references when the service stops.
    state.clear()


app = FastAPI(title="Mobil Churn API", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_sha": state["metadata"]["commit"],
    }
@app.post("/predict", response_model=Prediction)
def predict(customer: Customer):
    # Apply the same feature preparation used during training.
    row = pd.DataFrame([customer.model_dump()])
    features = skapa_features(row)[FEATURES]

    probability = state["model"].predict_proba(features)[0, 1]

    return Prediction(
        churn_probability=round(float(probability), 3),
        model_sha=state["metadata"]["commit"],
    )
