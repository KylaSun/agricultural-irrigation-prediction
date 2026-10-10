from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


class ModelContractError(ValueError):
    pass


@dataclass(frozen=True)
class PredictionResult:
    prediction: Any
    probability: float | None
    is_mock: bool
    label: str


class ModelAdapter:
    def __init__(self, model: Any, feature_order: Sequence[str], *, is_mock: bool = False):
        self.model = model
        self.feature_order = list(feature_order)
        self.is_mock = is_mock

    @classmethod
    def load(cls, path: str | Path, feature_order: Sequence[str]) -> "ModelAdapter":
        model_path = Path(path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if model_path.suffix.lower() in {".joblib", ".jl"}:
            try:
                import joblib
            except ImportError as exc:
                raise RuntimeError("joblib is required to load this model") from exc
            model = joblib.load(model_path)
        elif model_path.suffix.lower() in {".pkl", ".pickle"}:
            with model_path.open("rb") as handle:
                model = pickle.load(handle)
        else:
            raise ValueError("Supported model formats: .joblib, .jl, .pkl, .pickle")
        return cls(model, feature_order)

    def ordered_values(self, features: Mapping[str, Any]) -> list[Any]:
        missing_keys = [name for name in self.feature_order if name not in features]
        if missing_keys:
            raise ModelContractError(f"Missing feature keys: {', '.join(missing_keys)}")
        return [features[name] for name in self.feature_order]

    def predict(self, features: Mapping[str, Any]) -> PredictionResult:
        values = self.ordered_values(features)
        try:
            import pandas as pd
            matrix: Any = pd.DataFrame([values], columns=self.feature_order)
        except ImportError:
            matrix = [values]
        prediction = self.model.predict(matrix)[0]
        probability = None
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(matrix)[0]
            probability = float(probs[-1])
        return PredictionResult(prediction, probability, self.is_mock, str(prediction))


class MockModelAdapter(ModelAdapter):
    """Deterministic UI plumbing only; not trained and not an experiment result."""

    def __init__(self, feature_order: Sequence[str]):
        super().__init__(model=None, feature_order=feature_order, is_mock=True)

    def predict(self, features: Mapping[str, Any]) -> PredictionResult:
        self.ordered_values(features)
        soil = features.get("soil_moisture")
        rain = features.get("weather_rain")
        humidity = features.get("weather_humidity")
        score = 0.50
        if soil is not None:
            score += max(-0.25, min(0.25, (50.0 - float(soil)) / 100.0))
        if rain is not None:
            score -= min(0.20, float(rain) / 50.0)
        if humidity is not None:
            score += max(-0.10, min(0.10, (55.0 - float(humidity)) / 300.0))
        score = max(0.01, min(0.99, score))
        prediction = int(score >= 0.5)
        # The repository currently contains more than one possible target contract
        # (for example research `future_dry` versus a next-day irrigation event).
        # Keep the demo output neutral until the production model owner confirms it.
        label = f"MOCK: class={prediction} (target contract unconfirmed)"
        return PredictionResult(prediction, score, True, label)


def load_adapter(config_path: str | Path, mode: str, feature_order: Sequence[str]) -> ModelAdapter:
    with Path(config_path).open(encoding="utf-8") as handle:
        config = json.load(handle)[mode]
    if config.get("kind") == "mock" or not config.get("path"):
        return MockModelAdapter(feature_order)
    return ModelAdapter.load(config["path"], feature_order)
