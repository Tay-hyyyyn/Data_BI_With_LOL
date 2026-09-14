from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def build(rows: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    channels = rng.choice(["Search", "Social", "Display", "Affiliate"], rows, p=[0.35, 0.3, 0.2, 0.15])
    spend = rng.gamma(4.0, 130.0, rows).round(0)
    impressions = (spend * rng.uniform(60, 170, rows)).astype(int)
    ctr_base = np.select([channels == "Search", channels == "Social"], [0.045, 0.025], default=0.012)
    clicks = rng.binomial(impressions, np.clip(ctr_base + rng.normal(0, 0.004, rows), 0.002, 0.09))
    conversions = rng.binomial(clicks, np.clip(rng.normal(0.055, 0.012, rows), 0.005, 0.15))
    revenue = (conversions * rng.normal(58, 10, rows)).clip(0).round(0)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=rows, freq="h"),
        "campaign_id": [f"CMP-{i:05d}" for i in range(rows)],
        "channel": channels,
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "revenue": revenue,
        "roas": np.divide(revenue, spend, out=np.zeros(rows), where=spend != 0).round(3),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("samples/marketing_campaigns.csv"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build(args.rows, args.seed).to_csv(args.output, index=False, encoding="utf-8-sig")
    print(args.output.resolve())
