"""Pure-numpy inference for the FC estimation model (no TensorFlow dependency)."""
from __future__ import annotations

import json
import math
import os
from typing import Optional


def _elu(x: list[float]) -> list[float]:
    return [v if v > 0 else math.exp(v) - 1 for v in x]


def _matmul_bias(x: list[float], kernel: list[list[float]], bias: list[float]) -> list[float]:
    out = list(bias)
    for i, row in enumerate(x):
        for j, k in enumerate(kernel[i]):
            out[j] += row * k
    return out


class FCModel:
    """Lightweight FC estimator loaded from pre-extracted weights JSON."""

    def __init__(self, weights_path: str) -> None:
        with open(weights_path) as f:
            w = json.load(f)

        self._norm_in_mean = w["norm_in"]["mean"]
        self._norm_in_std = [math.sqrt(v + 1e-3) for v in w["norm_in"]["var"]]

        self._d1_k = w["d1"]["kernel"]
        self._d1_b = w["d1"]["bias"]
        self._d2_k = w["d2"]["kernel"]
        self._d2_b = w["d2"]["bias"]
        self._d3_k = w["d3"]["kernel"]
        self._d3_b = w["d3"]["bias"]

        self._norm_out_mean = w["norm_out"]["mean"][0]
        self._norm_out_std = math.sqrt(w["norm_out"]["var"][0] + 1e-3)

    def predict(self, orp: float, ph: float) -> float:
        x = [(orp - self._norm_in_mean[0]) / self._norm_in_std[0],
             (ph - self._norm_in_mean[1]) / self._norm_in_std[1]]

        x = _elu(_matmul_bias(x, self._d1_k, self._d1_b))
        x = _elu(_matmul_bias(x, self._d2_k, self._d2_b))
        x = _matmul_bias(x, self._d3_k, self._d3_b)

        return x[0] * self._norm_out_std + self._norm_out_mean


_model: Optional[FCModel] = None


def load_model() -> FCModel:
    global _model
    if _model is None:
        weights_path = os.path.join(os.path.dirname(__file__), "fc_model_weights.json")
        _model = FCModel(weights_path)
    return _model


def estimate_fc(orp: float, ph: float) -> Optional[float]:
    """Return FC estimate (ppm) or None on error."""
    try:
        return round(load_model().predict(orp, ph), 3)
    except Exception:
        return None
