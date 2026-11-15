"""CSV data upload and dataset management for backtesting."""
from __future__ import annotations

import io
import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])

# In-memory store for uploaded datasets: key → DataFrame
_datasets: dict[str, pd.DataFrame] = {}

# Required columns in uploaded CSV
_REQUIRED_COLS = {"open", "high", "low", "close", "volume"}

# Acceptable time column names
_TIME_COLS = {"time", "date", "datetime", "timestamp"}


@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    name: str = Form(""),
    symbol: str = Form("EURUSD"),
    timeframe: str = Form("H1"),
):
    """Upload a CSV file with OHLCV data for backtesting.

    CSV must have columns: open, high, low, close, volume
    Plus one of: time, date, datetime, timestamp
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "File must be a .csv")

    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Failed to parse CSV: {e}")

    # Normalize column names to lowercase
    df.columns = [c.strip().lower() for c in df.columns]

    # Check required columns
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise HTTPException(400, f"Missing required columns: {missing}")

    # Find and normalize the time column
    time_col = None
    for candidate in _TIME_COLS:
        if candidate in df.columns:
            time_col = candidate
            break

    if time_col is None:
        raise HTTPException(400, f"CSV must have a time column. Expected one of: {_TIME_COLS}")

    # Convert time column to unix seconds
    if time_col != "time":
        df = df.rename(columns={time_col: "time"})

    # Try parsing as datetime if not already numeric
    if not pd.api.types.is_numeric_dtype(df["time"]):
        try:
            df["time"] = pd.to_datetime(df["time"]).astype("int64") // 10**9
        except Exception as e:
            raise HTTPException(400, f"Failed to parse time column: {e}")

    # Keep only required columns
    df = df[["time", "open", "high", "low", "close", "volume"]].copy()

    # Drop NaN rows
    df = df.dropna().reset_index(drop=True)

    if len(df) < 50:
        raise HTTPException(400, f"CSV has only {len(df)} valid rows. Need at least 50.")

    # Store with a key
    dataset_name = name.strip() or file.filename.replace(".csv", "")
    key = f"{dataset_name}:{symbol}:{timeframe}"
    _datasets[key] = df

    logger.info("Uploaded dataset '%s': %d bars for %s %s", dataset_name, len(df), symbol, timeframe)

    return {
        "key": key,
        "name": dataset_name,
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": len(df),
    }


@router.get("/datasets")
async def list_datasets():
    """List all uploaded CSV datasets."""
    result = []
    for key, df in _datasets.items():
        parts = key.split(":", 2)
        result.append({
            "key": key,
            "name": parts[0] if len(parts) > 0 else key,
            "symbol": parts[1] if len(parts) > 1 else "?",
            "timeframe": parts[2] if len(parts) > 2 else "?",
            "bars": len(df),
        })
    return result


def get_dataset(key: str) -> pd.DataFrame:
    """Retrieve an uploaded dataset by key. Raises ValueError if not found."""
    if key not in _datasets:
        raise ValueError(f"Dataset '{key}' not found. Upload a CSV first.")
    return _datasets[key].copy()
