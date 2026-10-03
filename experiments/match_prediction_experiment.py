#!/usr/bin/env python3
"""Causal, time-ordered baselines for 2025 IVL Autumn match prediction.

The input has one row per half-round (小局).  A match result is reconstructed by
summing 主分 and 客分 within 大场序号.  Every feature used for match t is computed
only from matches/half-rounds strictly earlier than t.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


FEATURE_NAMES = [
    "elo_diff_scaled",
    "smoothed_win_rate_diff",
    "avg_point_margin_diff",
    "recent5_margin_diff",
    "hunter_margin_diff",
    "survivor_margin_diff",
    "head_to_head_margin",
]


@dataclass
class TeamState:
    matches: int = 0
    result_points: float = 0.0  # win=1, draw=0.5, loss=0
    point_margin_sum: float = 0.0
    hunter_margin_sum: float = 0.0
    hunter_halves: int = 0
    survivor_margin_sum: float = 0.0
    survivor_halves: int = 0
    recent_margins: deque = field(default_factory=lambda: deque(maxlen=5))


def sigmoid(x):
    x = np.clip(x, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-x))


def smoothed_rate(state: TeamState, alpha: float = 2.0) -> float:
    return (state.result_points + alpha) / (state.matches + 2.0 * alpha)


def safe_mean(total: float, count: int, prior_count: float = 3.0) -> float:
    return total / (count + prior_count)


def fit_ridge_logistic(x: np.ndarray, y: np.ndarray, ridge: float = 2.0):
    """Small IRLS implementation; accepts draws as soft targets y=0.5."""
    means = x.mean(axis=0)
    scales = x.std(axis=0)
    scales[scales < 1e-8] = 1.0
    z = (x - means) / scales
    z = np.column_stack([np.ones(len(z)), z])
    beta = np.zeros(z.shape[1])
    penalty = np.eye(z.shape[1]) * ridge
    penalty[0, 0] = 0.05
    for _ in range(40):
        p = sigmoid(z @ beta)
        w = np.clip(p * (1.0 - p), 1e-5, None)
        hessian = z.T @ (z * w[:, None]) + penalty
        gradient = z.T @ (y - p) - penalty @ beta
        step = np.linalg.solve(hessian, gradient)
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta, means, scales


def logistic_predict(model, x: np.ndarray) -> float:
    beta, means, scales = model
    z = np.r_[1.0, (x - means) / scales]
    return float(sigmoid(z @ beta))


def fit_bradley_terry(history, teams, ridge: float = 2.0):
    """Regularized batch Bradley-Terry fit on all strictly previous matches."""
    team_index = {team: i for i, team in enumerate(teams)}
    x = np.zeros((len(history), len(teams)))
    y = np.zeros(len(history))
    for row_i, row in enumerate(history):
        x[row_i, team_index[row["home"]]] = 1.0
        x[row_i, team_index[row["away"]]] = -1.0
        y[row_i] = row["target"]
    # Add a home/listing-side intercept. Identifiability is supplied by ridge.
    x = np.column_stack([np.ones(len(x)), x])
    beta = np.zeros(x.shape[1])
    penalty = np.eye(x.shape[1]) * ridge
    penalty[0, 0] = 0.1
    for _ in range(40):
        p = sigmoid(x @ beta)
        w = np.clip(p * (1.0 - p), 1e-5, None)
        hessian = x.T @ (x * w[:, None]) + penalty
        gradient = x.T @ (y - p) - penalty @ beta
        step = np.linalg.solve(hessian, gradient)
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta, team_index


def bt_predict(model, home: str, away: str) -> float:
    beta, team_index = model
    value = beta[0] + beta[1 + team_index[home]] - beta[1 + team_index[away]]
    return float(sigmoid(value))


def reconstruct_matches(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.copy()
    raw["日期"] = pd.to_datetime(raw["日期"])
    grouped = raw.groupby("大场序号", sort=False)
    matches = grouped.agg(
        date=("日期", "first"),
        time=("具体时间", "first"),
        home=("主场", "first"),
        away=("客场", "first"),
        home_score=("主分", "sum"),
        away_score=("客分", "sum"),
        half_rounds=("小局唯一ID", "count"),
    ).reset_index()
    matches = matches.sort_values(["date", "time", "大场序号"]).reset_index(drop=True)
    matches["margin"] = matches["home_score"] - matches["away_score"]
    matches["target"] = np.where(matches["margin"] > 0, 1.0, np.where(matches["margin"] < 0, 0.0, 0.5))
    return matches


def causal_predictions(raw: pd.DataFrame, matches: pd.DataFrame, warmup: int):
    teams = sorted(set(matches["home"]) | set(matches["away"]))
    state = defaultdict(TeamState)
    elo = defaultdict(lambda: 1500.0)
    h2h_margins = defaultdict(list)
    feature_history = []
    target_history = []
    bt_history = []
    output = []

    rows_by_match = {key: value for key, value in raw.groupby("大场序号")}

    for i, match in matches.iterrows():
        home, away = match["home"], match["away"]
        hs, aws = state[home], state[away]
        home_rate, away_rate = smoothed_rate(hs), smoothed_rate(aws)
        recent_h = np.mean(hs.recent_margins) if hs.recent_margins else 0.0
        recent_a = np.mean(aws.recent_margins) if aws.recent_margins else 0.0
        pair_key = tuple(sorted((home, away)))
        prior_pair = h2h_margins[pair_key]
        if prior_pair:
            # Margins are stored from lexicographically first team's perspective.
            h2h_home = np.mean(prior_pair) * (1.0 if home == pair_key[0] else -1.0)
        else:
            h2h_home = 0.0

        x = np.array([
            (elo[home] - elo[away]) / 400.0,
            home_rate - away_rate,
            (safe_mean(hs.point_margin_sum, hs.matches) - safe_mean(aws.point_margin_sum, aws.matches)) / 10.0,
            (recent_h - recent_a) / 10.0,
            (safe_mean(hs.hunter_margin_sum, hs.hunter_halves) - safe_mean(aws.hunter_margin_sum, aws.hunter_halves)) / 4.0,
            (safe_mean(hs.survivor_margin_sum, hs.survivor_halves) - safe_mean(aws.survivor_margin_sum, aws.survivor_halves)) / 4.0,
            h2h_home / 10.0,
        ])

        elo_p = float(1.0 / (1.0 + 10.0 ** ((elo[away] - elo[home]) / 400.0)))
        win_rate_p = float(sigmoid(3.0 * (home_rate - away_rate)))
        if len(bt_history) >= 12:
            bt_p = bt_predict(fit_bradley_terry(bt_history, teams), home, away)
        else:
            bt_p = 0.5
        if len(feature_history) >= 20:
            form_p = logistic_predict(
                fit_ridge_logistic(np.vstack(feature_history), np.array(target_history)), x
            )
        else:
            form_p = 0.5
        ensemble_p = (elo_p + bt_p + form_p) / 3.0

        output.append({
            "match_number": int(match["大场序号"]),
            "chronological_index": i + 1,
            "date": match["date"].strftime("%Y-%m-%d"),
            "home": home,
            "away": away,
            "home_score": int(match["home_score"]),
            "away_score": int(match["away_score"]),
            "actual": "主胜" if match["target"] == 1 else ("客胜" if match["target"] == 0 else "平局"),
            "is_test": bool(i >= warmup),
            **{name: float(value) for name, value in zip(FEATURE_NAMES, x)},
            "p_home_win_rate": win_rate_p,
            "p_home_elo": elo_p,
            "p_home_bradley_terry": bt_p,
            "p_home_form_logistic": form_p,
            "p_home_ensemble": ensemble_p,
        })

        # Update all state only after predictions are recorded.
        y = float(match["target"])
        feature_history.append(x)
        target_history.append(y)
        bt_history.append({"home": home, "away": away, "target": y})
        margin = float(match["margin"])
        for team, result_points, team_margin in [(home, y, margin), (away, 1.0 - y, -margin)]:
            s = state[team]
            s.matches += 1
            s.result_points += result_points
            s.point_margin_sum += team_margin
            s.recent_margins.append(team_margin)

        k = 28.0
        elo_delta = k * (y - elo_p)
        elo[home] += elo_delta
        elo[away] -= elo_delta

        stored_margin = margin if home == pair_key[0] else -margin
        h2h_margins[pair_key].append(stored_margin)

        for _, game in rows_by_match[int(match["大场序号"])].iterrows():
            hunter = game["监管方队伍"]
            survivor = game["求生方队伍"]
            side_margin = float(game["监管方得分"] - game["求生方得分"])
            state[hunter].hunter_margin_sum += side_margin
            state[hunter].hunter_halves += 1
            state[survivor].survivor_margin_sum -= side_margin
            state[survivor].survivor_halves += 1

    return pd.DataFrame(output), dict(elo), state


def evaluate(predictions: pd.DataFrame):
    test = predictions[predictions["is_test"] & (predictions["actual"] != "平局")].copy()
    y = (test["actual"] == "主胜").astype(float).to_numpy()
    methods = {
        "恒定0.5基线（并列时判主胜）": np.full(len(test), 0.5),
        "历史胜率": test["p_home_win_rate"].to_numpy(),
        "Elo": test["p_home_elo"].to_numpy(),
        "Bradley-Terry": test["p_home_bradley_terry"].to_numpy(),
        "因果状态逻辑回归": test["p_home_form_logistic"].to_numpy(),
        "三模型等权集成": test["p_home_ensemble"].to_numpy(),
    }
    rows = []
    for name, p in methods.items():
        p = np.clip(p, 1e-6, 1 - 1e-6)
        correct = ((p >= 0.5) == (y == 1.0)).astype(float)
        accuracy = correct.mean()
        n = len(y)
        z = 1.96
        denom = 1 + z * z / n
        center = (accuracy + z * z / (2 * n)) / denom
        radius = z * math.sqrt(accuracy * (1 - accuracy) / n + z * z / (4 * n * n)) / denom
        rows.append({
            "method": name,
            "n_non_draw_test": n,
            "accuracy": accuracy,
            "accuracy_ci95_low": center - radius,
            "accuracy_ci95_high": center + radius,
            "log_loss": float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()),
            "brier": float(np.mean((p - y) ** 2)),
        })
    return pd.DataFrame(rows).sort_values(["log_loss", "accuracy"], ascending=[True, False])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="Data/Data_details_All_games_details.csv")
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--output-dir", default="experiments/results")
    args = parser.parse_args()

    raw = pd.read_csv(args.input, encoding="utf-8-sig", skiprows=1)
    matches = reconstruct_matches(raw)
    predictions, final_elo, state = causal_predictions(raw, matches, args.warmup)
    metrics = evaluate(predictions)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(out_dir / "walk_forward_predictions.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(out_dir / "model_metrics.csv", index=False, encoding="utf-8-sig")

    summary = {
        "input_rows": int(len(raw)),
        "matches": int(len(matches)),
        "teams": int(len(final_elo)),
        "date_min": matches["date"].min().strftime("%Y-%m-%d"),
        "date_max": matches["date"].max().strftime("%Y-%m-%d"),
        "home_wins": int((matches["target"] == 1).sum()),
        "away_wins": int((matches["target"] == 0).sum()),
        "draws": int((matches["target"] == 0.5).sum()),
        "warmup_matches": args.warmup,
        "test_matches": int((predictions["is_test"]).sum()),
        "test_non_draw_matches": int(((predictions["is_test"]) & (predictions["actual"] != "平局")).sum()),
        "final_elo": dict(sorted(final_elo.items(), key=lambda item: item[1], reverse=True)),
    }
    (out_dir / "experiment_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n", metrics.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()

