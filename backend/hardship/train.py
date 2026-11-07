"""Train the hardship early-warning models.

    python -m backend.hardship.train            # ~2-3 min, writes backend/hardship/model/

1. Simulate N random UK households for 16 months (LCF-calibrated spending).
2. Take snapshots; features from the history up to the snapshot, labels from
   what actually happens next: does the balance go below £0 within 30/60/90 days?
3. Train one LightGBM classifier per horizon with monotone constraints (so the
   explanations always point the sensible way), evaluate on held-out households,
   and write a fairness report by income band and income type.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from .features import FEATURE_NAMES, MONOTONE, compute_features
from .simulate import random_profile, simulate

MODEL_DIR = Path(__file__).resolve().parent / "model"
HORIZONS = (30, 60, 90)
N_DAYS = 480
START = date(2025, 1, 1)


def _one(idx: int, seed: int, snaps_per: int) -> list[dict]:
    rng = np.random.default_rng(seed * 100_003 + idx)
    p = random_profile(rng, idx)
    tx, bal = simulate(p, START, N_DAYS, seed=seed * 7 + idx)
    out = []
    for snap in rng.integers(180, N_DAYS - max(HORIZONS) - 1, size=snaps_per):
        as_of = bal.index[snap]
        feats = compute_features(tx[tx["date"] <= as_of], float(bal.iloc[snap]), as_of)
        row = {"household": idx, "income_kind": p.income_kind, "monthly_income": p.monthly_income, **feats}
        for h in HORIZONS:
            row[f"y{h}"] = int(bal.iloc[snap + 1: snap + h + 1].min() < 0)
        out.append(row)
    return out


def build_dataset(n: int, seed: int = 42, snaps_per: int = 3, workers: int = 8) -> pd.DataFrame:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        parts = ex.map(_one, range(n), [seed] * n, [snaps_per] * n, chunksize=25)
        rows = [r for part in parts for r in part]
    return pd.DataFrame(rows)


PARAMS = dict(
    objective="binary",
    learning_rate=0.05,
    num_leaves=15,
    min_data_in_leaf=40,
    feature_fraction=0.9,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=1.0,
    monotone_constraints=MONOTONE,
    monotone_constraints_method="advanced",
    verbose=-1,
    seed=7,
)


def income_band(x: pd.Series) -> pd.Series:
    return pd.cut(x, [0, 1200, 2000, 3000, np.inf], labels=["<£1.2k", "£1.2k-2k", "£2k-3k", "£3k+"])


def fairness_table(df: pd.DataFrame, p: np.ndarray, y: np.ndarray, by: pd.Series) -> list[dict]:
    out = []
    for g, idx in df.groupby(by, observed=True).groups.items():
        m = df.index.get_indexer(idx)
        yy, pp = y[m], p[m]
        out.append({
            "group": str(g),
            "n": int(len(m)),
            "observed_rate": round(float(yy.mean()), 3),
            "mean_predicted": round(float(pp.mean()), 3),
            "auc": round(float(roc_auc_score(yy, pp)), 3) if 0 < yy.mean() < 1 else None,
            "flag_rate_high": round(float((pp >= 0.35).mean()), 3),
            "precision_high": round(float(yy[pp >= 0.35].mean()), 3) if (pp >= 0.35).any() else None,
        })
    return out


def main(n: int = 3000, seed: int = 42):
    t0 = datetime.now()
    df = build_dataset(n, seed)
    print(f"dataset: {len(df)} snapshots from {n} households in {(datetime.now() - t0).seconds}s")
    for h in HORIZONS:
        print(f"  base rate overdrawn within {h}d: {df[f'y{h}'].mean():.3f}")

    test_mask = (df["household"] % 5 == 0).to_numpy()  # hold out whole households
    tr, te = df[~test_mask].reset_index(drop=True), df[test_mask].reset_index(drop=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": "synthetic UK households, spending calibrated to ONS LCF FYE2025 (see calibration.py)",
        "n_households": n, "n_snapshots": len(df), "features": FEATURE_NAMES, "horizons": {},
    }
    for h in HORIZONS:
        y = f"y{h}"
        dtr = lgb.Dataset(tr[FEATURE_NAMES], tr[y])
        dva = lgb.Dataset(te[FEATURE_NAMES], te[y], reference=dtr)
        booster = lgb.train(PARAMS, dtr, num_boost_round=600, valid_sets=[dva],
                            callbacks=[lgb.early_stopping(40, verbose=False)])
        p = booster.predict(te[FEATURE_NAMES], num_iteration=booster.best_iteration)
        booster.save_model(str(MODEL_DIR / f"hardship_{h}d.txt"), num_iteration=booster.best_iteration)
        yt = te[y].to_numpy()
        # the honest early-warning metric: people who have not been overdrawn at all recently
        fresh = (te["days_overdrawn_90d"] == 0).to_numpy()
        report["horizons"][f"{h}d"] = {
            "base_rate_train": round(float(tr[y].mean()), 4),
            "test_auc": round(float(roc_auc_score(yt, p)), 4),
            "test_auc_not_recently_overdrawn": round(float(roc_auc_score(yt[fresh], p[fresh])), 4),
            "base_rate_not_recently_overdrawn": round(float(yt[fresh].mean()), 4),
            "test_brier": round(float(brier_score_loss(yt, p)), 4),
            "best_iteration": booster.best_iteration,
            "fairness_by_income_band": fairness_table(te, p, yt, income_band(te["monthly_income"])),
            "fairness_by_income_type": fairness_table(te, p, yt, te["income_kind"]),
        }
        r = report["horizons"][f"{h}d"]
        print(f"  {h}d: AUC {r['test_auc']} (not recently overdrawn: {r['test_auc_not_recently_overdrawn']}, "
              f"base {r['base_rate_not_recently_overdrawn']}), Brier {r['test_brier']}")
    (MODEL_DIR / "report.json").write_text(json.dumps(report, indent=2))
    print(f"saved to {MODEL_DIR}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    main(a.n, a.seed)
