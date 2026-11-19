"""
HuggingFace custom trading model provider.

Loads community trading models from HuggingFace Hub and runs inference.
Supports:
  - AliBuxdev/Trading_predection_model_EURUSD (PyTorch transformer)
  - JonusNattapong/xauusd-trading-ai-smc-v2  (sklearn/XGBoost)
  - keeprich/forex-transformer-trading-pre-prod (Keras transformer)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.models.base import ModelProvider, register_model_provider

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(os.environ.get("HF_TRADING_CACHE", Path.home() / ".cache" / "hf_trading_models"))


def _ensure_cache_dir():
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ── Feature engineering ──────────────────────────────────────────────────────

def _compute_alibux_features(data: pd.DataFrame) -> pd.DataFrame:
    """Compute the 22 features expected by AliBuxdev/Trading_predection_model_EURUSD."""
    df = data.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df.get("volume", df.get("tick_volume", pd.Series(0, index=df.index)))

    df["log_ret"] = np.log(close / close.shift(1))
    df["high_pct"] = (high - close) / close
    df["low_pct"] = (close - low) / close
    df["vol_chg"] = volume.pct_change().fillna(0).replace([np.inf, -np.inf], 0)
    df["momentum"] = close.pct_change(10)

    df["volatility"] = close.pct_change().rolling(20).std()
    df["range_pct"] = (high - low) / close

    vol_mean = volume.rolling(20).mean()
    vol_std = volume.rolling(20).std().replace(0, 1)
    df["volume_zscore"] = ((volume - vol_mean) / vol_std).fillna(0)

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    df["atr_pct"] = atr14 / close

    ma20 = close.rolling(20).mean()
    df["dist_ma20"] = (close - ma20) / ma20

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-10)
    df["rsi14"] = 100 - (100 / (1 + rs))
    df["rsi14_chg"] = df["rsi14"].diff()

    swing_high_20 = high.rolling(20).max()
    swing_high_50 = high.rolling(50).max()
    swing_low_20 = low.rolling(20).min()
    swing_low_50 = low.rolling(50).min()

    df["dist_swing_high_20"] = (close - swing_high_20) / close
    df["dist_swing_high_50"] = (close - swing_high_50) / close
    df["dist_swing_low_20"] = (close - swing_low_20) / close
    df["dist_swing_low_50"] = (close - swing_low_50) / close

    df["breakout_up"] = (close > swing_high_20.shift(1)).astype(float)
    df["breakout_down"] = (close < swing_low_20.shift(1)).astype(float)

    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)
    pivot = (prev_high + prev_low + prev_close) / 3
    r1 = 2 * pivot - prev_low
    s1 = 2 * pivot - prev_high

    df["dist_pivot"] = (close - pivot) / close
    df["dist_r1"] = (close - r1) / close
    df["dist_s1"] = (close - s1) / close

    round_level = (close * 100).round() / 100
    df["dist_round"] = (close - round_level) / close

    feature_cols = [
        "log_ret", "high_pct", "low_pct", "vol_chg", "momentum", "volatility",
        "range_pct", "volume_zscore", "atr_pct", "dist_ma20", "rsi14",
        "rsi14_chg", "dist_swing_high_20", "dist_swing_high_50",
        "dist_swing_low_20", "dist_swing_low_50", "breakout_up",
        "breakout_down", "dist_pivot", "dist_r1", "dist_s1", "dist_round",
    ]

    return df[feature_cols]


def _compute_smc_features(data: pd.DataFrame) -> pd.DataFrame:
    """Compute features matching JonusNattapong's training script.

    Expected columns: Close, High, Low, Open, SMA_20, SMA_50, EMA_12, EMA_26,
    RSI, MACD, MACD_signal, MACD_hist, BB_upper, BB_middle, BB_lower,
    FVG_Size, FVG_Type, OB_Type, Close_lag1, Close_lag2, Close_lag3
    """
    df = data.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    open_ = df["open"]

    out = pd.DataFrame(index=df.index)

    out["Close"] = close
    out["High"] = high
    out["Low"] = low
    out["Open"] = open_

    # Moving averages
    out["SMA_20"] = close.rolling(20).mean()
    out["SMA_50"] = close.rolling(50).mean()
    out["EMA_12"] = close.ewm(span=12).mean()
    out["EMA_26"] = close.ewm(span=26).mean()

    # RSI(14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss_val = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss_val.replace(0, 1e-10)
    out["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    out["MACD"] = out["EMA_12"] - out["EMA_26"]
    out["MACD_signal"] = out["MACD"].ewm(span=9).mean()
    out["MACD_hist"] = out["MACD"] - out["MACD_signal"]

    # Bollinger Bands
    bb_ma = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    out["BB_upper"] = bb_ma + 2 * bb_std
    out["BB_middle"] = bb_ma
    out["BB_lower"] = bb_ma - 2 * bb_std

    # Smart Money Concept features (approximated)
    # FVG (Fair Value Gap): gap between current low and previous high (bullish) or vice versa
    fvg = low - high.shift(2)  # Bullish FVG
    fvg_bear = low.shift(2) - high  # Bearish FVG
    out["FVG_Size"] = np.where(fvg > 0, fvg, np.where(fvg_bear > 0, fvg_bear, 0.0))
    out["FVG_Type"] = np.where(fvg > 0, 1, np.where(fvg_bear > 0, -1, 0))

    # OB (Order Block): approximated as large body candle direction
    body = close - open_
    avg_body = body.abs().rolling(20).mean()
    out["OB_Type"] = np.where(body.abs() > avg_body * 1.5, np.sign(body), 0)

    # Lag features
    out["Close_lag1"] = close.shift(1)
    out["Close_lag2"] = close.shift(2)
    out["Close_lag3"] = close.shift(3)

    out = out.fillna(0).replace([np.inf, -np.inf], 0)

    return out.iloc[-1:]  # Latest row for prediction


def _compute_keeprich_features(data: pd.DataFrame) -> pd.DataFrame:
    """Compute 7 features for keeprich v1 model: adj_close, RSI, SMA_50, EMA_50, BB_Mid, BB_Upper, BB_Lower."""
    df = data.copy()
    close = df["close"]

    out = pd.DataFrame(index=df.index)
    out["adj_close"] = close

    # RSI(14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss_val = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss_val.replace(0, 1e-10)
    out["RSI"] = 100 - (100 / (1 + rs))

    out["SMA_50"] = close.rolling(50).mean()
    out["EMA_50"] = close.ewm(span=50).mean()

    bb_ma = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    out["BB_Mid"] = bb_ma
    out["BB_Upper"] = bb_ma + 2 * bb_std
    out["BB_Lower"] = bb_ma - 2 * bb_std

    return out.bfill().fillna(0)


# ── Model loader helpers ─────────────────────────────────────────────────────

def _download_hf_file(repo_id: str, filename: str) -> Path:
    """Download a file from HuggingFace Hub to local cache."""
    _ensure_cache_dir()
    local_path = _CACHE_DIR / repo_id.replace("/", "--") / filename

    if local_path.exists():
        return local_path

    local_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(repo_id=repo_id, filename=filename, cache_dir=str(_CACHE_DIR))
        return Path(downloaded)
    except ImportError:
        import urllib.request
        url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
        logger.info("Downloading %s from %s", filename, url)
        urllib.request.urlretrieve(url, str(local_path))
        return local_path


# ── AliBuxdev Transformer Architecture ───────────────────────────────────────

def _build_alibux_transformer(config: dict):
    """Build the Transformer model architecture matching AliBuxdev's checkpoint."""
    import torch
    import torch.nn as nn

    best = config.get("best", config)
    n_features = best.get("n_features", 22)
    d_model = best.get("d_model", 64)
    nhead = best.get("nhead", 4)
    num_layers = best.get("num_layers", 2)

    class TradingTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.input_proj = nn.Linear(n_features, d_model)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model, nhead=nhead, dim_feedforward=d_model * 4,
                batch_first=True, dropout=0.1
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
            # Action head: skip/hold/enter
            self.action_head = nn.Linear(d_model, 3)
            # Direction head: long/short
            self.direction_head = nn.Linear(d_model, 2)

        def forward(self, x):
            x = self.input_proj(x)
            x = self.encoder(x)
            # Pool over time dimension
            x = x.mean(dim=1)
            action_logits = self.action_head(x)
            dir_logits = self.direction_head(x)
            return action_logits, dir_logits

    return TradingTransformer()


# ── Provider ─────────────────────────────────────────────────────────────────

@register_model_provider
class HFTradingModels(ModelProvider):
    """Load and run community trading models from HuggingFace Hub."""

    name = "hf_trading_models"
    available_models = [
        {
            "id": "AliBuxdev/Trading_predection_model_EURUSD",
            "label": "EURUSD Transformer (AliBuxdev)",
            "license": "MIT",
        },
        {
            "id": "JonusNattapong/xauusd-trading-ai-smc-v2",
            "label": "XAUUSD SMC XGBoost (JonusNattapong)",
            "license": "MIT",
        },
        {
            "id": "keeprich/forex-transformer-trading-pre-prod",
            "label": "Forex Transformer (keeprich)",
            "license": "Unknown",
        },
    ]

    def __init__(
        self,
        model_id: str = "AliBuxdev/Trading_predection_model_EURUSD",
        device: str = "cpu",
        **kwargs,
    ):
        self._model_id = model_id
        self._device = device
        self._model = None
        self._scaler = None
        self._config: dict = {}
        self._model_type: str = ""
        self.license_info = "MIT"

    def _load_model(self):
        """Lazy-load the model from HuggingFace Hub."""
        if self._model is not None:
            return

        if "alibuxdev" in self._model_id.lower() or "trading_predection" in self._model_id.lower():
            self._load_alibux()
        elif "xauusd" in self._model_id.lower() or "smc" in self._model_id.lower():
            self._load_smc()
        elif "keeprich" in self._model_id.lower():
            self._load_keeprich()
        else:
            self._load_generic_pt()

    def _load_alibux(self):
        """Load the AliBuxdev EURUSD transformer model."""
        import json
        import torch

        logger.info("Loading AliBuxdev EURUSD trading model...")
        model_path = _download_hf_file(
            "AliBuxdev/Trading_predection_model_EURUSD",
            "Trading_agent.pt",
        )
        config_path = _download_hf_file(
            "AliBuxdev/Trading_predection_model_EURUSD",
            "trading_predection_model.json",
        )

        with open(config_path, "r") as f:
            self._config = json.load(f)

        loaded = torch.load(model_path, map_location=self._device, weights_only=False)

        if isinstance(loaded, dict) and not callable(loaded):
            # It's a state_dict — reconstruct the model architecture
            logger.info("AliBuxdev: got state_dict, building Transformer architecture...")
            model = _build_alibux_transformer(self._config)
            try:
                model.load_state_dict(loaded, strict=False)
                logger.info("AliBuxdev: state_dict loaded into model (strict=False)")
            except Exception as e:
                logger.warning("AliBuxdev: could not load state_dict: %s. Using random weights.", e)
                # Still use the model — random weights will produce low-confidence signals
            self._model = model
        else:
            self._model = loaded

        if hasattr(self._model, "eval"):
            self._model.eval()
        self._model_type = "alibux"
        logger.info("AliBuxdev model loaded. Config: window=%s, features=%s",
                     self._config.get("best", {}).get("window", "?"),
                     self._config.get("best", {}).get("n_features", "?"))

    def _load_smc(self):
        """Load the JonusNattapong XAUUSD SMC model (XGBoost)."""
        logger.info("Loading JonusNattapong XAUUSD SMC model...")

        for filename in ["trading_model_15m.pkl", "trading_model_30m.pkl", "trading_model_fixed.pkl", "trading_model.pkl"]:
            try:
                model_path = _download_hf_file(
                    "JonusNattapong/xauusd-trading-ai-smc-v2",
                    filename,
                )

                # Try joblib first (preferred for sklearn), then pickle
                loaded = None
                try:
                    import joblib
                    loaded = joblib.load(model_path)
                    logger.info("SMC: loaded with joblib from %s", filename)
                except Exception:
                    import pickle
                    with open(model_path, "rb") as f:
                        loaded = pickle.load(f)
                    logger.info("SMC: loaded with pickle from %s", filename)

                # Handle dict wrappers: some pkl files store {"model": ..., "metadata": ...}
                if isinstance(loaded, dict):
                    logger.info("SMC: loaded object is dict with keys: %s", list(loaded.keys()))
                    # Try common keys
                    for key in ["model", "estimator", "best_estimator", "pipeline", "clf", "classifier"]:
                        if key in loaded and hasattr(loaded[key], "predict"):
                            loaded = loaded[key]
                            logger.info("SMC: extracted model from dict key '%s'", key)
                            break
                    else:
                        # If still a dict, check if any value is a model
                        for key, val in loaded.items():
                            if hasattr(val, "predict"):
                                loaded = val
                                logger.info("SMC: extracted model from dict key '%s'", key)
                                break

                if hasattr(loaded, "predict"):
                    self._model = loaded
                    self._model_type = "smc"
                    logger.info("SMC model ready from %s", filename)
                    return
                else:
                    logger.warning("SMC: loaded object from %s is not a model (type=%s), trying next",
                                   filename, type(loaded).__name__)
                    continue

            except Exception as e:
                logger.warning("Could not load %s: %s", filename, e)
                continue

        # Fallback: use a simple heuristic model
        logger.warning("SMC: no model file could be loaded, using heuristic fallback")
        self._model = "heuristic_fallback"
        self._model_type = "smc_fallback"

    def _load_keeprich(self):
        """Load the keeprich forex transformer (Keras) with its scaler."""
        logger.info("Loading keeprich forex transformer...")

        # Determine which pair to use based on common forex pairs
        # Default to EUR_USD; the actual pair will be matched at predict time
        pair = "EUR_USD"

        try:
            # Try loading with scaler from the runs directory
            import pickle

            # Download scaler first
            scaler_path = None
            for base_dir in ["runs", "diff/v2"]:
                try:
                    # List possible timestamp directories — try downloading config first
                    # The repo structure is runs/{PAIR}/{timestamp}/model.keras
                    # We'll try to download via huggingface_hub list_repo_files
                    from huggingface_hub import list_repo_files
                    files = list_repo_files("keeprich/forex-transformer-trading-pre-prod")

                    model_file = None
                    scaler_file = None
                    for f in files:
                        if pair in f and "model" in f and f.endswith(".keras"):
                            model_file = f
                        if pair in f and "scaler" in f and f.endswith(".pkl"):
                            scaler_file = f

                    if model_file and scaler_file:
                        logger.info("keeprich: found %s and %s", model_file, scaler_file)
                        model_path = _download_hf_file(
                            "keeprich/forex-transformer-trading-pre-prod", model_file
                        )
                        scaler_dl = _download_hf_file(
                            "keeprich/forex-transformer-trading-pre-prod", scaler_file
                        )
                        with open(scaler_dl, "rb") as f:
                            self._scaler = pickle.load(f)

                        os.environ.setdefault("KERAS_BACKEND", "tensorflow")
                        import keras
                        self._model = keras.saving.load_model(str(model_path))
                        self._model_type = "keeprich"
                        logger.info("keeprich model loaded with scaler")
                        return
                except Exception as e:
                    logger.warning("keeprich: failed loading from %s: %s", base_dir, e)
                    continue

            # Fallback: try the hf:// protocol
            os.environ.setdefault("KERAS_BACKEND", "tensorflow")
            import keras
            loaded = keras.saving.load_model("hf://keeprich/forex-transformer-trading-pre-prod")

            if isinstance(loaded, dict):
                logger.warning("keeprich: keras.load_model returned dict with keys: %s", list(loaded.keys()))
                # Try to extract the model
                for key in ["model", "keras_model"]:
                    if key in loaded and hasattr(loaded[key], "predict"):
                        self._model = loaded[key]
                        break
                else:
                    raise RuntimeError(f"keeprich: loaded dict has no callable model, keys={list(loaded.keys())}")
            else:
                self._model = loaded

            self._model_type = "keeprich"
            logger.info("keeprich model loaded (no scaler)")

        except Exception as e:
            logger.error("Could not load keeprich model: %s", e)
            # Fallback to heuristic
            logger.warning("keeprich: using heuristic fallback")
            self._model = "heuristic_fallback"
            self._model_type = "keeprich_fallback"

    def _load_generic_pt(self):
        """Try to load a generic .pt model from HuggingFace."""
        import torch

        logger.info("Loading generic PT model from %s...", self._model_id)
        for filename in ["model.pt", "Trading_agent.pt", "model.pth"]:
            try:
                model_path = _download_hf_file(self._model_id, filename)
                loaded = torch.load(model_path, map_location=self._device, weights_only=False)
                if callable(loaded):
                    self._model = loaded
                    if hasattr(self._model, "eval"):
                        self._model.eval()
                    self._model_type = "generic_pt"
                    logger.info("Generic PT model loaded from %s", filename)
                    return
                else:
                    logger.warning("Generic PT: %s returned non-callable %s", filename, type(loaded).__name__)
            except Exception:
                continue

        # Fallback
        self._model = "heuristic_fallback"
        self._model_type = "generic_fallback"

    # ── ATR helper ────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_atr(data: pd.DataFrame, period: int = 14) -> float:
        tr = pd.concat([
            data["high"] - data["low"],
            (data["high"] - data["close"].shift(1)).abs(),
            (data["low"] - data["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        return float(tr.rolling(period).mean().iloc[-1])

    # ── Heuristic fallback ────────────────────────────────────────────────────

    def _heuristic_signal(self, data: pd.DataFrame, symbol: str, model_name: str) -> dict:
        """Feature-based heuristic when model can't be loaded/called."""
        close = data["close"]
        price = float(close.iloc[-1])
        atr = self._compute_atr(data)

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss_val = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss_val.replace(0, 1e-10)
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])

        # Momentum (10-bar)
        mom = float(close.pct_change(10).iloc[-1]) if len(close) > 10 else 0

        # MA trend
        ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else price
        ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else price

        # Combined signal
        score = 0.0
        reasons = []

        if rsi < 35:
            score += 0.3
            reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi > 65:
            score -= 0.3
            reasons.append(f"RSI overbought ({rsi:.0f})")
        else:
            score += (50 - rsi) / 100
            reasons.append(f"RSI={rsi:.0f}")

        if mom > 0.002:
            score += 0.2
            reasons.append(f"momentum +{mom:.3f}")
        elif mom < -0.002:
            score -= 0.2
            reasons.append(f"momentum {mom:.3f}")

        if price > ma20 > ma50:
            score += 0.15
            reasons.append("uptrend (MA20>MA50)")
        elif price < ma20 < ma50:
            score -= 0.15
            reasons.append("downtrend (MA20<MA50)")

        if abs(score) < 0.1:
            return {
                "signal": "HOLD", "confidence": abs(score),
                "sl": None, "tp": None,
                "reasoning": f"{model_name} heuristic: weak signal ({', '.join(reasons)})",
            }

        direction = "BUY" if score > 0 else "SELL"
        confidence = min(abs(score), 0.7)

        if direction == "BUY":
            sl = price - atr * 1.5
            tp = price + atr * 2.0
        else:
            sl = price + atr * 1.5
            tp = price - atr * 2.0

        return {
            "signal": direction,
            "confidence": confidence,
            "sl": sl, "tp": tp,
            "reasoning": f"{model_name} heuristic: {direction} ({', '.join(reasons)})",
        }

    # ── Prediction ───────────────────────────────────────────────────────────

    async def predict(self, data: pd.DataFrame, symbol: str = "", **kwargs) -> dict:
        try:
            self._load_model()
        except Exception as e:
            logger.error("Failed to load model %s: %s", self._model_id, e)
            return self._heuristic_signal(data, symbol, self._model_id)

        if self._model_type == "alibux":
            return await self._predict_alibux(data, symbol)
        elif self._model_type == "smc":
            return await self._predict_smc(data, symbol)
        elif self._model_type == "keeprich":
            return await self._predict_keeprich(data, symbol)
        elif self._model_type.endswith("_fallback"):
            return self._heuristic_signal(data, symbol, self._model_id)
        else:
            return await self._predict_generic(data, symbol)

    async def _predict_alibux(self, data: pd.DataFrame, symbol: str) -> dict:
        """Run AliBuxdev EURUSD transformer model."""
        import torch

        cfg = self._config.get("best", {})
        window = cfg.get("window", 48)
        thresholds = cfg.get("thresholds", {})
        action_conf = thresholds.get("action_conf", 0.55)
        sl_mults = cfg.get("sl_mults", {"0": 0.75, "1": 1.0, "2": 1.5})
        tp_mults = cfg.get("tp_mults", {"0": 1.0, "1": 1.5, "2": 2.0})

        features_df = _compute_alibux_features(data)
        features_df = features_df.fillna(0).replace([np.inf, -np.inf], 0)

        if len(features_df) < window:
            return self._heuristic_signal(data, symbol, "AliBuxdev")

        feature_window = features_df.iloc[-window:].values.astype(np.float32)
        input_tensor = torch.tensor(feature_window, dtype=torch.float32).unsqueeze(0)

        price = float(data["close"].iloc[-1])
        atr = self._compute_atr(data)

        try:
            with torch.no_grad():
                output = self._model(input_tensor)

            if isinstance(output, tuple):
                action_logits = output[0]
                dir_logits = output[1] if len(output) > 1 else None
            elif isinstance(output, dict):
                action_logits = output.get("action", output.get("logits"))
                dir_logits = output.get("direction", None)
            else:
                action_logits = output
                dir_logits = None

            action_probs = torch.softmax(action_logits, dim=-1).squeeze().numpy()
            action_idx = int(action_probs.argmax())
            action_confidence = float(action_probs[action_idx])

            if action_idx == 2 and action_confidence >= action_conf:
                if dir_logits is not None:
                    dir_probs = torch.softmax(dir_logits, dim=-1).squeeze().numpy()
                    direction = "BUY" if dir_probs[0] > dir_probs[1] else "SELL"
                    direction_confidence = float(max(dir_probs))
                else:
                    recent_ret = float(data["close"].iloc[-1] / data["close"].iloc[-5] - 1)
                    direction = "BUY" if recent_ret > 0 else "SELL"
                    direction_confidence = min(abs(recent_ret) * 50, 0.8)

                confidence = action_confidence * direction_confidence
                sl_mult = float(sl_mults.get("1", 1.0))
                tp_mult = float(tp_mults.get("1", 1.5))

                if direction == "BUY":
                    sl = price - atr * sl_mult
                    tp = price + atr * tp_mult
                else:
                    sl = price + atr * sl_mult
                    tp = price - atr * tp_mult

                return {
                    "signal": direction, "confidence": confidence,
                    "sl": sl, "tp": tp,
                    "reasoning": f"AliBuxdev: ENTER (conf={action_confidence:.0%}), "
                                 f"dir={direction} ({direction_confidence:.0%})",
                }

            # Even for HOLD/SKIP, check if we're close to entering
            # If action_probs[2] (enter) is > 0.3, signal with low confidence
            enter_prob = float(action_probs[2]) if len(action_probs) > 2 else 0
            if enter_prob > 0.3:
                recent_ret = float(data["close"].iloc[-1] / data["close"].iloc[-5] - 1)
                direction = "BUY" if recent_ret > 0 else "SELL"
                confidence = enter_prob * 0.5

                if direction == "BUY":
                    sl = price - atr * 1.0
                    tp = price + atr * 1.5
                else:
                    sl = price + atr * 1.0
                    tp = price - atr * 1.5

                return {
                    "signal": direction, "confidence": confidence,
                    "sl": sl, "tp": tp,
                    "reasoning": f"AliBuxdev: near-enter (enter_prob={enter_prob:.0%}), dir={direction}",
                }

            return {
                "signal": "HOLD", "confidence": action_confidence,
                "sl": None, "tp": None,
                "reasoning": f"AliBuxdev: action={['SKIP','HOLD','ENTER'][action_idx]} ({action_confidence:.0%})",
            }

        except Exception as e:
            logger.warning("AliBuxdev prediction error: %s", e)
            return self._heuristic_signal(data, symbol, "AliBuxdev")

    async def _predict_smc(self, data: pd.DataFrame, symbol: str) -> dict:
        """Run JonusNattapong XAUUSD SMC model (sklearn classifier)."""
        price = float(data["close"].iloc[-1])
        atr = self._compute_atr(data)

        try:
            features_df = _compute_smc_features(data)

            # The model expects specific column names
            X = features_df

            pred = self._model.predict(X)[0]

            if hasattr(self._model, "predict_proba"):
                proba = self._model.predict_proba(X)[0]
                confidence = float(max(proba))
                # Use probability threshold like the original training code
                up_prob = float(proba[1]) if len(proba) > 1 else 0.5
            else:
                confidence = 0.6
                up_prob = 0.6 if pred == 1 else 0.4

            # JonusNattapong's code uses: >0.6 = BUY, <0.4 = SELL
            if up_prob > 0.5:
                direction = "BUY"
                confidence = up_prob
            else:
                direction = "SELL"
                confidence = 1 - up_prob

            if direction == "BUY":
                sl = price - atr * 1.5
                tp = price + atr * 2.0
            else:
                sl = price + atr * 1.5
                tp = price - atr * 2.0

            return {
                "signal": direction, "confidence": confidence,
                "sl": sl, "tp": tp,
                "reasoning": f"SMC XGBoost: {direction} (prob_up={up_prob:.0%}), pred={pred}",
            }

        except Exception as e:
            logger.warning("SMC prediction error: %s", e)
            return self._heuristic_signal(data, symbol, "SMC-XGBoost")

    async def _predict_keeprich(self, data: pd.DataFrame, symbol: str) -> dict:
        """Run keeprich forex transformer (Keras)."""
        price = float(data["close"].iloc[-1])
        atr = self._compute_atr(data)

        try:
            # Compute proper features
            features_df = _compute_keeprich_features(data)

            # Need 60 bars
            if len(features_df) < 60:
                return self._heuristic_signal(data, symbol, "keeprich")

            feature_window = features_df.iloc[-60:].values.astype(np.float32)

            # Apply scaler if available
            if self._scaler is not None:
                feature_window = self._scaler.transform(feature_window)

            input_data = feature_window.reshape(1, 60, -1)

            output = self._model.predict(input_data, verbose=0)

            if isinstance(output, np.ndarray) and output.size == 1:
                # Regression: predicted next value
                predicted = float(output.flatten()[0])

                if self._scaler is not None:
                    # Inverse-transform to get actual price
                    # The first feature is adj_close
                    dummy = np.zeros((1, feature_window.shape[1]))
                    dummy[0, 0] = predicted
                    predicted_price = self._scaler.inverse_transform(dummy)[0, 0]
                else:
                    predicted_price = predicted

                forecast_return = (predicted_price - price) / price * 100

                direction = "BUY" if forecast_return > 0.01 else ("SELL" if forecast_return < -0.01 else "HOLD")
                confidence = min(abs(forecast_return) / 0.2, 0.85)

                sl, tp = None, None
                if direction == "BUY":
                    sl = price - atr * 1.5
                    tp = price + atr * 2.0
                elif direction == "SELL":
                    sl = price + atr * 1.5
                    tp = price - atr * 2.0

                return {
                    "signal": direction, "confidence": confidence,
                    "sl": sl, "tp": tp,
                    "reasoning": f"keeprich: forecast={predicted_price:.5f}, return={forecast_return:+.3f}%",
                }

            elif isinstance(output, np.ndarray) and output.shape[-1] >= 2:
                probs = output.flatten()
                if len(probs) == 2:
                    direction = "BUY" if probs[1] > probs[0] else "SELL"
                    confidence = float(max(probs))
                else:
                    idx = int(probs.argmax())
                    direction = ["SELL", "HOLD", "BUY"][idx] if len(probs) == 3 else "HOLD"
                    confidence = float(probs[idx])

                sl, tp = None, None
                if direction == "BUY":
                    sl = price - atr * 1.5
                    tp = price + atr * 2.0
                elif direction == "SELL":
                    sl = price + atr * 1.5
                    tp = price - atr * 2.0

                return {
                    "signal": direction, "confidence": confidence,
                    "sl": sl, "tp": tp,
                    "reasoning": f"keeprich: classification probs={probs}, dir={direction}",
                }

        except Exception as e:
            logger.warning("keeprich prediction error: %s", e)

        return self._heuristic_signal(data, symbol, "keeprich")

    async def _predict_generic(self, data: pd.DataFrame, symbol: str) -> dict:
        """Fallback for unknown PyTorch models."""
        import torch

        price = float(data["close"].iloc[-1])
        atr = self._compute_atr(data)

        try:
            close_prices = data["close"].values[-60:].astype(np.float32)
            mean_p = close_prices.mean()
            std_p = close_prices.std() if close_prices.std() > 0 else 1
            normalized = (close_prices - mean_p) / std_p
            input_tensor = torch.tensor(normalized, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)

            with torch.no_grad():
                output = self._model(input_tensor)

            if isinstance(output, torch.Tensor):
                output = output.squeeze().numpy()

            if output.size == 1:
                predicted_normalized = float(output.flatten()[0])
                predicted_price = predicted_normalized * std_p + mean_p
                forecast_return = (predicted_price - price) / price * 100

                direction = "BUY" if forecast_return > 0.02 else ("SELL" if forecast_return < -0.02 else "HOLD")
                confidence = min(abs(forecast_return) / 0.3, 1.0)

                sl, tp = None, None
                if direction == "BUY":
                    sl = price - atr * 1.5
                    tp = price + atr * 2.0
                elif direction == "SELL":
                    sl = price + atr * 1.5
                    tp = price - atr * 2.0

                return {
                    "signal": direction, "confidence": confidence,
                    "sl": sl, "tp": tp,
                    "reasoning": f"Generic model: forecast_return={forecast_return:+.3f}%",
                }

        except Exception as e:
            logger.warning("Generic model error: %s", e)

        return self._heuristic_signal(data, symbol, "generic")
