"""
==============================================================================
 MLB Inference Engine  --  Poisson + Skellam Probabilistic Model
 ==============================================================================
 Author  : Senior Data Scientist (Probabilistic Modelling)
 Module  : models/mlb_engine.py
 ==============================================================================

 MATHEMATICAL FOUNDATION
 -----------------------

 This module implements two complementary probability distributions for
 predicting MLB game outcomes:

 1. POISSON DISTRIBUTION  (run-scoring model)
    ------------------------------------------
    The number of runs a team scores follows a Poisson process:

        P(X = k) = (lambda^k * e^(-lambda)) / k!

    where lambda = expected runs/game, estimated from:
        lambda = team_avg_runs_scored * (lg_avg_runs / opp_avg_runs_allowed)

    This "log5-style" adjustment accounts for the opposing pitching quality.
    If a team averages 5.0 R/G against a staff that allows 4.0 R/G (vs the
    league avg of 4.53), the adjusted lambda = 5.0 * (4.53 / 4.0) = 5.66.

 2. SKELLAM DISTRIBUTION  (run-differential model)
    -----------------------------------------------
    If X ~ Poisson(lambda_A) and Y ~ Poisson(lambda_B) are independent,
    then D = X - Y follows a Skellam distribution:

        P(D = k) = e^(-(lA + lB)) * (lA/lB)^(k/2) * I_|k|(2*sqrt(lA*lB))

    where I_|k| is the modified Bessel function of the first kind, order |k|.
    (scipy.special.iv)

    This gives us EXACT margin-of-victory probabilities:
      P(A wins by 1) = P(D = 1)
      P(A wins by 2) = P(D = 2)
      P(A wins by 3) = P(D = 3)
      P(A wins by 3+) = sum P(D = k) for k >= 4

 3. MONEYLINE (win probability)
    ---------------------------
    P(A wins) = sum P(D = k) for k = 1, 2, 3, ...
    P(B wins) = sum P(D = k) for k = -1, -2, -3, ...
    P(tie) is redistributed proportionally since MLB has no ties.

 Usage
 -----
     python -m models.mlb_engine
     python -m models.mlb_engine --team-a-runs 5.2 --team-b-runs 4.1

==============================================================================
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

import numpy as np
from scipy.stats import poisson
from scipy.special import iv as bessel_iv   # Modified Bessel function I_v(z)


# ==============================================================================
#  Constants
# ==============================================================================

# League average runs per game (2024-2025 MLB)
LEAGUE_AVG_RPG = 4.53

# Maximum runs to consider per team in the probability matrix (0..MAX_RUNS)
MAX_RUNS = 12

# Maximum margin of victory to compute individually
MAX_MARGIN = 15

# Home-field advantage in runs (empirical: ~0.11 R/G)
HOME_FIELD_RUNS = 0.11


# ==============================================================================
#  Data Structures
# ==============================================================================

@dataclass
class TeamInput:
    """
    Input parameters for one team in a matchup.

    Attributes
    ----------
    name : str
        Team name (e.g., 'New York Yankees').
    avg_runs_scored : float
        Season average runs scored per game by this team.
    avg_runs_allowed : float
        Season average runs allowed per game by this team's pitching.
    is_home : bool
        Whether this team plays at home.
    """
    name: str
    avg_runs_scored: float
    avg_runs_allowed: float
    is_home: bool = False


@dataclass
class InferenceResult:
    """
    Structured output of the inference engine.

    This object serializes directly to the required JSON schema.
    """
    winner: str
    predicted_score: dict          # {"team_a": X, "team_b": Y}
    win_probability: float         # percentage 0-100
    margins: dict                  # {"win_by_1": %, "win_by_2": %, ...}
    details: dict                  # extended analytics

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a formatted JSON string."""
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False)

    def to_dict(self) -> dict:
        """Return as a plain dictionary."""
        return asdict(self)


# ==============================================================================
#  CORE FUNCTIONS
# ==============================================================================

def adjust_lambda(
    team_avg_runs: float,
    opp_avg_runs_allowed: float,
    league_avg: float = LEAGUE_AVG_RPG,
    is_home: bool = False,
) -> float:
    """
    Calculate the adjusted Poisson lambda (expected runs) for a team.

    The adjustment accounts for the opposing pitching quality relative
    to the league average. This is the "log5" normalization widely used
    in sabermetric projection systems (PECOTA, ZiPS, Steamer).

    Formula
    -------
        lambda = team_R/G * (league_avg / opp_RA/G)

    If a team scores 5.0 R/G and faces a staff that allows 3.8 R/G
    (vs league avg 4.53):

        lambda = 5.0 * (4.53 / 3.8) = 5.96

    If the same team faces a bad staff allowing 5.5 R/G:

        lambda = 5.0 * (4.53 / 5.5) = 4.12

    Parameters
    ----------
    team_avg_runs : float
        Team's season average runs scored per game.
    opp_avg_runs_allowed : float
        Opponent's season average runs allowed per game.
    league_avg : float
        MLB league-average runs per game (default: 4.53).
    is_home : bool
        Add home-field advantage (~0.11 R/G).

    Returns
    -------
    float
        Adjusted lambda, clamped to [1.5, 12.0].

    Notes
    -----
    The clamp prevents degenerate Poisson distributions:
    - lambda < 1.5 would imply near-shutout every game (unrealistic)
    - lambda > 12.0 would be an extreme outlier environment
    """
    if opp_avg_runs_allowed <= 0:
        opp_avg_runs_allowed = league_avg  # safety fallback

    lam = team_avg_runs * (league_avg / opp_avg_runs_allowed)

    if is_home:
        lam += HOME_FIELD_RUNS

    return max(1.5, min(12.0, lam))


# ------------------------------------------------------------------------------
#  1. POISSON RUN PROBABILITY MATRIX
# ------------------------------------------------------------------------------

def predict_runs(
    avg_runs_team: float,
    avg_runs_allowed_opp: float,
    is_home: bool = False,
    max_runs: int = MAX_RUNS,
) -> np.ndarray:
    """
    Compute the probability of scoring exactly k runs (k = 0 .. max_runs)
    for a single team, using the Poisson distribution.

    The Poisson PMF is:

        P(X = k) = e^(-lambda) * lambda^k / k!

    where lambda is the adjusted expected runs.

    Parameters
    ----------
    avg_runs_team : float
        Team's season average runs scored per game.
    avg_runs_allowed_opp : float
        Opposing team's season average runs allowed per game.
    is_home : bool
        Whether the batting team plays at home.
    max_runs : int
        Upper bound of the run count (default: 12).

    Returns
    -------
    np.ndarray
        Array of shape (max_runs + 1,) where index k holds P(X = k).
        Sum is approximately 1.0 (tail probability beyond max_runs
        is negligible for realistic lambdas).

    Example
    -------
    >>> probs = predict_runs(5.2, 4.0)
    >>> print(f"P(score exactly 5) = {probs[5]:.4f}")
    P(score exactly 5) = 0.1668
    """
    lam = adjust_lambda(avg_runs_team, avg_runs_allowed_opp, is_home=is_home)

    # Vectorized Poisson PMF via scipy
    k_values = np.arange(0, max_runs + 1)
    probabilities = poisson.pmf(k_values, lam)

    return probabilities


def build_joint_matrix(
    lambda_a: float,
    lambda_b: float,
    max_runs: int = MAX_RUNS,
) -> np.ndarray:
    """
    Build the joint probability matrix P(team_A = i, team_B = j)
    for all score combinations (i, j) in [0..max_runs] x [0..max_runs].

    Under the independence assumption (each team's scoring is an
    independent Poisson process):

        P(A=i, B=j) = P(A=i) * P(B=j)

    Parameters
    ----------
    lambda_a : float
        Poisson lambda for Team A.
    lambda_b : float
        Poisson lambda for Team B.
    max_runs : int
        Max runs per team.

    Returns
    -------
    np.ndarray
        Matrix of shape (max_runs+1, max_runs+1).
        Element [i][j] = P(A scores i AND B scores j).
    """
    k = np.arange(0, max_runs + 1)
    probs_a = poisson.pmf(k, lambda_a)
    probs_b = poisson.pmf(k, lambda_b)
    return np.outer(probs_a, probs_b)


# ------------------------------------------------------------------------------
#  2. SKELLAM DISTRIBUTION  (Run Differential)
# ------------------------------------------------------------------------------

def skellam_pmf(k: int, lambda_a: float, lambda_b: float) -> float:
    """
    Compute the Skellam probability mass function at point k.

    The Skellam distribution models the difference D = X - Y where
    X ~ Poisson(lambda_a) and Y ~ Poisson(lambda_b) are independent.

    Formula
    -------
        P(D = k) = e^(-(lA + lB)) * (lA / lB)^(k/2) * I_|k|(2 * sqrt(lA * lB))

    Where:
        - I_|k| is the modified Bessel function of the first kind, order |k|
        - This is computed via scipy.special.iv(|k|, z)

    The modified Bessel function I_v(z) is defined as:

        I_v(z) = sum_{m=0}^{inf} (1 / (m! * Gamma(m+v+1))) * (z/2)^(2m+v)

    For integer orders, Gamma(m+v+1) = (m+v)!, giving:

        I_n(z) = sum_{m=0}^{inf} (z/2)^(2m+n) / (m! * (m+n)!)

    Parameters
    ----------
    k : int
        The run differential to evaluate.
        k > 0  means Team A wins by k runs.
        k < 0  means Team B wins by |k| runs.
        k = 0  means a tie.
    lambda_a : float
        Poisson lambda for Team A.
    lambda_b : float
        Poisson lambda for Team B.

    Returns
    -------
    float
        P(X - Y = k), the probability of a run differential of exactly k.

    Notes
    -----
    For numerical stability when lambda_a or lambda_b is very small,
    we use the log-space computation:

        log P(D=k) = -(lA + lB) + (k/2)*log(lA/lB) + log(I_|k|(2*sqrt(lA*lB)))

    This avoids overflow in the ratio (lA/lB)^(k/2) for extreme k values.
    """
    if lambda_a <= 0 or lambda_b <= 0:
        return 0.0

    # Argument for the Bessel function: z = 2 * sqrt(lambda_a * lambda_b)
    z = 2.0 * math.sqrt(lambda_a * lambda_b)

    # Log-space computation for numerical stability
    #   log P(D=k) = -(lA+lB) + (k/2)*log(lA/lB) + log(I_|k|(z))
    log_exp_term = -(lambda_a + lambda_b)
    log_ratio_term = (k / 2.0) * math.log(lambda_a / lambda_b)

    # Modified Bessel function of the first kind, order |k|
    bessel_value = float(bessel_iv(abs(k), z))

    if bessel_value <= 0:
        return 0.0

    log_bessel = math.log(bessel_value)
    log_prob = log_exp_term + log_ratio_term + log_bessel

    return math.exp(log_prob)


def compute_margin_probabilities(
    lambda_a: float,
    lambda_b: float,
    max_margin: int = MAX_MARGIN,
) -> dict:
    """
    Compute the probability of each victory margin using the Skellam
    distribution.

    Returns probabilities from Team A's perspective:
        P(A - B = +1) : A wins by 1
        P(A - B = +2) : A wins by 2
        P(A - B = +3) : A wins by 3
        P(A - B > +3) : A wins by 4 or more
        P(A - B = -1) : B wins by 1
        P(A - B = -2) : B wins by 2
        ... etc.

    Parameters
    ----------
    lambda_a : float
        Adjusted Poisson lambda for Team A.
    lambda_b : float
        Adjusted Poisson lambda for Team B.
    max_margin : int
        Maximum individual margin to compute (default: 15).

    Returns
    -------
    dict
        Keys: 'win_by_1', 'win_by_2', 'win_by_3', 'win_by_3_plus',
              'lose_by_1', 'lose_by_2', 'lose_by_3', 'lose_by_3_plus',
              'tie', 'full_distribution'
    """
    # Compute individual margin probabilities for Team A perspective
    margins = {}
    for d in range(-max_margin, max_margin + 1):
        margins[d] = skellam_pmf(d, lambda_a, lambda_b)

    # Named buckets
    win_by_1 = margins.get(1, 0.0)
    win_by_2 = margins.get(2, 0.0)
    win_by_3 = margins.get(3, 0.0)
    win_by_3_plus = sum(margins.get(d, 0.0) for d in range(4, max_margin + 1))

    lose_by_1 = margins.get(-1, 0.0)
    lose_by_2 = margins.get(-2, 0.0)
    lose_by_3 = margins.get(-3, 0.0)
    lose_by_3_plus = sum(margins.get(d, 0.0) for d in range(-max_margin, -3))

    tie = margins.get(0, 0.0)

    return {
        "win_by_1": round(win_by_1 * 100, 2),
        "win_by_2": round(win_by_2 * 100, 2),
        "win_by_3": round(win_by_3 * 100, 2),
        "win_by_3_plus": round(win_by_3_plus * 100, 2),
        "lose_by_1": round(lose_by_1 * 100, 2),
        "lose_by_2": round(lose_by_2 * 100, 2),
        "lose_by_3": round(lose_by_3 * 100, 2),
        "lose_by_3_plus": round(lose_by_3_plus * 100, 2),
        "tie": round(tie * 100, 2),
        "full_distribution": {
            str(d): round(margins[d] * 100, 4) for d in sorted(margins.keys())
            if margins[d] > 0.0001
        },
    }


# ------------------------------------------------------------------------------
#  3. MONEYLINE PROBABILITY
# ------------------------------------------------------------------------------

def get_moneyline_probability(
    lambda_a: float,
    lambda_b: float,
    max_margin: int = MAX_MARGIN,
) -> dict:
    """
    Calculate the moneyline (win) probability for each team by summing
    all Skellam probabilities where one team's score exceeds the other.

    From Team A's perspective:

        P(A wins) = SUM_{k=1}^{inf} P(D = k)    [D = X_A - X_B]
        P(B wins) = SUM_{k=1}^{inf} P(D = -k)
        P(tie)    = P(D = 0)

    Since MLB has no ties, we redistribute the tie probability
    proportionally:

        P(A wins | no tie) = P(A wins) / (P(A wins) + P(B wins))

    This is mathematically equivalent to computing the moneyline from
    the joint Poisson matrix but uses the analytically exact Skellam
    PMF rather than a truncated numerical grid.

    Parameters
    ----------
    lambda_a : float
        Adjusted expected runs for Team A.
    lambda_b : float
        Adjusted expected runs for Team B.
    max_margin : int
        Maximum margin to compute in the Skellam sum.

    Returns
    -------
    dict
        {
            'team_a_win_prob': float (0-1),
            'team_b_win_prob': float (0-1),
            'tie_prob_raw': float (before redistribution),
            'team_a_implied_odds': str (American odds),
            'team_b_implied_odds': str (American odds),
        }
    """
    # Sum over all positive margins for A's win probability
    a_win_raw = sum(skellam_pmf(k, lambda_a, lambda_b) for k in range(1, max_margin + 1))

    # Sum over all negative margins for B's win probability
    b_win_raw = sum(skellam_pmf(-k, lambda_a, lambda_b) for k in range(1, max_margin + 1))

    # Tie probability
    tie_raw = skellam_pmf(0, lambda_a, lambda_b)

    # Redistribute ties proportionally (MLB rule: no ties)
    total_decided = a_win_raw + b_win_raw
    if total_decided > 0:
        a_win = a_win_raw + tie_raw * (a_win_raw / total_decided)
        b_win = b_win_raw + tie_raw * (b_win_raw / total_decided)
    else:
        a_win = 0.5
        b_win = 0.5

    # Normalize to ensure sum = 1.0 (handles tail truncation)
    total = a_win + b_win
    a_win /= total
    b_win /= total

    return {
        "team_a_win_prob": round(a_win, 6),
        "team_b_win_prob": round(b_win, 6),
        "tie_prob_raw": round(tie_raw, 6),
        "team_a_implied_odds": _prob_to_american(a_win),
        "team_b_implied_odds": _prob_to_american(b_win),
    }


def _prob_to_american(prob: float) -> str:
    """
    Convert a win probability to American (moneyline) odds format.

    If prob >= 50%  ->  negative odds:  -(prob / (1 - prob)) * 100
    If prob < 50%   ->  positive odds:  +((1 - prob) / prob) * 100

    Examples
    --------
    0.60 -> "-150"
    0.40 -> "+150"
    0.50 -> "-100"           (pick'em)
    """
    if prob <= 0 or prob >= 1:
        return "N/A"
    if prob >= 0.5:
        odds = -(prob / (1 - prob)) * 100
        return f"{odds:+.0f}"
    else:
        odds = ((1 - prob) / prob) * 100
        return f"{odds:+.0f}"


# ==============================================================================
#  UNIFIED PREDICTION FUNCTION  (JSON output)
# ==============================================================================

def predict_matchup(
    team_a: TeamInput,
    team_b: TeamInput,
    ou_line: Optional[float] = None,
) -> InferenceResult:
    """
    Run the full inference pipeline and return a structured JSON result.

    Pipeline
    --------
    1. Adjust lambdas (log5 normalization)
    2. Build Poisson run probability vectors (0-12 runs)
    3. Build joint score matrix and find predicted score
    4. Compute Skellam margin probabilities
    5. Compute moneyline probabilities
    6. Compute over/under
    7. Package into JSON-serializable InferenceResult

    Parameters
    ----------
    team_a : TeamInput
        First team (conventionally the "favorite" or away team).
    team_b : TeamInput
        Second team (conventionally the "underdog" or home team).
    ou_line : float, optional
        Over/under line to evaluate. Auto-calculated if None.

    Returns
    -------
    InferenceResult
        Fully structured result with .to_json() and .to_dict() methods.
    """
    # --- Step 1: Adjust lambdas ---
    lambda_a = adjust_lambda(
        team_a.avg_runs_scored,
        team_b.avg_runs_allowed,
        is_home=team_a.is_home,
    )
    lambda_b = adjust_lambda(
        team_b.avg_runs_scored,
        team_a.avg_runs_allowed,
        is_home=team_b.is_home,
    )

    # --- Step 2: Poisson run probabilities (0-12 for each team) ---
    probs_a = poisson.pmf(np.arange(0, MAX_RUNS + 1), lambda_a)
    probs_b = poisson.pmf(np.arange(0, MAX_RUNS + 1), lambda_b)

    # --- Step 3: Joint score matrix & predicted score ---
    joint = build_joint_matrix(lambda_a, lambda_b)

    # Find the most likely score
    max_idx = np.unravel_index(np.argmax(joint), joint.shape)
    predicted_score_a = int(max_idx[0])
    predicted_score_b = int(max_idx[1])

    # Top 8 most likely scores
    flat_indices = np.argsort(joint.ravel())[::-1][:8]
    top_scores = {}
    for idx in flat_indices:
        sa, sb = divmod(idx, MAX_RUNS + 1)
        top_scores[f"{int(sa)}-{int(sb)}"] = round(float(joint[sa, sb]) * 100, 2)

    # --- Step 4: Skellam margin probabilities ---
    margins = compute_margin_probabilities(lambda_a, lambda_b)

    # --- Step 5: Moneyline ---
    moneyline = get_moneyline_probability(lambda_a, lambda_b)

    # Determine the winner
    if moneyline["team_a_win_prob"] > moneyline["team_b_win_prob"]:
        winner = team_a.name
        win_prob = moneyline["team_a_win_prob"]
    else:
        winner = team_b.name
        win_prob = moneyline["team_b_win_prob"]

    # --- Step 6: Over/Under ---
    total_lambda = lambda_a + lambda_b
    if ou_line is None:
        ou_line = round(total_lambda * 2) / 2  # nearest 0.5

    total_k = np.arange(0, 2 * MAX_RUNS + 1)
    total_probs = poisson.pmf(total_k, total_lambda)
    over_prob = float(np.sum(total_probs[total_k > ou_line]))
    under_prob = float(np.sum(total_probs[total_k < ou_line]))

    # --- Step 7: Build result ---
    result = InferenceResult(
        winner=winner,
        predicted_score={
            "team_a": predicted_score_a,
            "team_a_name": team_a.name,
            "team_b": predicted_score_b,
            "team_b_name": team_b.name,
        },
        win_probability=round(win_prob * 100, 2),
        margins={
            "win_by_1": margins["win_by_1"],
            "win_by_2": margins["win_by_2"],
            "win_by_3": margins["win_by_3"],
            "win_by_3_plus": margins["win_by_3_plus"],
        },
        details={
            "lambda_a": round(lambda_a, 4),
            "lambda_b": round(lambda_b, 4),
            "team_a_run_probs": {
                str(k): round(float(probs_a[k]) * 100, 2) for k in range(MAX_RUNS + 1)
            },
            "team_b_run_probs": {
                str(k): round(float(probs_b[k]) * 100, 2) for k in range(MAX_RUNS + 1)
            },
            "moneyline": {
                "team_a": {
                    "name": team_a.name,
                    "win_prob": round(moneyline["team_a_win_prob"] * 100, 2),
                    "american_odds": moneyline["team_a_implied_odds"],
                },
                "team_b": {
                    "name": team_b.name,
                    "win_prob": round(moneyline["team_b_win_prob"] * 100, 2),
                    "american_odds": moneyline["team_b_implied_odds"],
                },
            },
            "over_under": {
                "line": ou_line,
                "over_prob": round(over_prob * 100, 2),
                "under_prob": round(under_prob * 100, 2),
                "projected_total": round(total_lambda, 2),
            },
            "top_scores": top_scores,
            "skellam_margins_full": margins,
        },
    )

    return result


# ==============================================================================
#  CONSOLE DEMO  --  Yankees vs Dodgers
# ==============================================================================

def run_demo():
    """
    Simulate a Yankees vs Dodgers matchup using the inference engine.

    Uses 2025 season averages:
      - NYY: 5.12 R/G scored, 3.98 R/G allowed
      - LAD: 4.87 R/G scored, 3.65 R/G allowed

    These are pulled from the team's overall performance, not
    lineup-specific (see mlb_lineup_evaluator.py for that granularity).
    """
    # Try to pull actual team-level stats from the database
    team_a_runs, team_a_allowed = 5.12, 3.98  # NYY defaults
    team_b_runs, team_b_allowed = 4.87, 3.65  # LAD defaults

    try:
        from services.config import DATABASE_URL
        from services.models import get_engine
        from sqlalchemy import text
        from sqlalchemy.orm import sessionmaker

        engine = get_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Compute team-level averages from batter/pitcher tables
            for abbr, defaults in [("NYY", "a"), ("LAD", "b")]:
                row = conn.execute(text(
                    "SELECT AVG(ops) as avg_ops, AVG(woba) as avg_woba "
                    "FROM mlb_player_batting "
                    "WHERE team = :team AND season = 2025"
                ), {"team": abbr}).fetchone()
                if row and row[0]:
                    # Use OPS as a proxy for run environment
                    avg_ops = float(row[0])
                    # Rough conversion: R/G ~ OPS * 6.5 (empirical)
                    est_rpg = avg_ops * 6.5
                    if defaults == "a":
                        team_a_runs = round(est_rpg, 2)
                    else:
                        team_b_runs = round(est_rpg, 2)

                row_p = conn.execute(text(
                    "SELECT AVG(fip) as avg_fip "
                    "FROM mlb_player_pitching "
                    "WHERE team = :team AND season = 2025"
                ), {"team": abbr}).fetchone()
                if row_p and row_p[0]:
                    avg_fip = float(row_p[0])
                    if defaults == "a":
                        team_a_allowed = round(avg_fip, 2)
                    else:
                        team_b_allowed = round(avg_fip, 2)

        print("[DB] Team stats loaded from PostgreSQL.")
    except Exception as e:
        print(f"[FALLBACK] Using hardcoded stats: {e}")

    # Build team inputs
    yankees = TeamInput(
        name="New York Yankees",
        avg_runs_scored=team_a_runs,
        avg_runs_allowed=team_a_allowed,
        is_home=False,
    )
    dodgers = TeamInput(
        name="Los Angeles Dodgers",
        avg_runs_scored=team_b_runs,
        avg_runs_allowed=team_b_allowed,
        is_home=True,
    )

    W = 72

    print()
    print("=" * W)
    print("  MLB INFERENCE ENGINE  --  Probabilistic Model".center(W))
    print("  New York Yankees  @  Los Angeles Dodgers".center(W))
    print("=" * W)
    print()

    # Show team inputs
    print(f"  Team A: {yankees.name}")
    print(f"    R/G Scored:  {yankees.avg_runs_scored:.2f}")
    print(f"    R/G Allowed: {yankees.avg_runs_allowed:.2f}")
    print(f"    Home: {yankees.is_home}")
    print()
    print(f"  Team B: {dodgers.name}")
    print(f"    R/G Scored:  {dodgers.avg_runs_scored:.2f}")
    print(f"    R/G Allowed: {dodgers.avg_runs_allowed:.2f}")
    print(f"    Home: {dodgers.is_home}")
    print()

    # --- Run prediction ---
    print("-" * W)
    print("  RUNNING INFERENCE...".center(W))
    print("-" * W)
    print()

    result = predict_matchup(yankees, dodgers, ou_line=8.5)

    # --- Display Poisson run probabilities ---
    print("  [1] POISSON RUN PROBABILITY VECTORS (0-12 runs)")
    print("  " + "-" * 60)
    print(f"  {'Runs':>5}  {'NYY Prob':>10}  {'LAD Prob':>10}  {'Poisson Bar':>20}")
    print(f"  {'----':>5}  {'--------':>10}  {'--------':>10}  {'-' * 20}")

    for k in range(MAX_RUNS + 1):
        pa = result.details["team_a_run_probs"][str(k)]
        pb = result.details["team_b_run_probs"][str(k)]
        bar_a = "#" * int(pa / 2)
        print(f"  {k:>5}  {pa:>9.2f}%  {pb:>9.2f}%  {bar_a}")

    # --- Display Skellam margins ---
    print()
    print(f"  [2] SKELLAM DISTRIBUTION (Run Differentials)")
    print("  " + "-" * 60)
    margins = result.margins
    print(f"  P(NYY wins by 1):    {margins['win_by_1']:>6.2f}%")
    print(f"  P(NYY wins by 2):    {margins['win_by_2']:>6.2f}%")
    print(f"  P(NYY wins by 3):    {margins['win_by_3']:>6.2f}%")
    print(f"  P(NYY wins by 3+):   {margins['win_by_3_plus']:>6.2f}%")
    print()

    # Full Skellam distribution (compact)
    skellam_full = result.details["skellam_margins_full"]["full_distribution"]
    print(f"  Full Skellam PDF (significant values):")
    for diff_str, prob in sorted(skellam_full.items(), key=lambda x: int(x[0])):
        d = int(diff_str)
        if prob > 0.5:  # only show > 0.5%
            label = "NYY+" if d > 0 else ("TIE" if d == 0 else "LAD+")
            bar = "#" * int(prob / 1.5)
            print(f"    D={d:>+3d}  ({label}{abs(d) if d != 0 else '':>2})  {prob:>6.2f}%  {bar}")

    # --- Moneyline ---
    print()
    print(f"  [3] MONEYLINE PROBABILITIES")
    print("  " + "-" * 60)
    ml = result.details["moneyline"]
    a_wp = ml["team_a"]["win_prob"]
    b_wp = ml["team_b"]["win_prob"]
    print(f"  {ml['team_a']['name']:<25} {a_wp:>6.2f}%   {ml['team_a']['american_odds']}")
    print(f"  {ml['team_b']['name']:<25} {b_wp:>6.2f}%   {ml['team_b']['american_odds']}")

    # --- O/U ---
    print()
    ou = result.details["over_under"]
    print(f"  [4] OVER/UNDER")
    print("  " + "-" * 60)
    print(f"  Projected Total:  {ou['projected_total']:.1f} runs")
    print(f"  Line:             {ou['line']:.1f}")
    print(f"  OVER  {ou['line']}:       {ou['over_prob']:.1f}%")
    print(f"  UNDER {ou['line']}:       {ou['under_prob']:.1f}%")

    # --- Final JSON ---
    print()
    print("=" * W)
    print("  STRUCTURED JSON OUTPUT".center(W))
    print("=" * W)
    print()
    print(result.to_json(indent=2))
    print()

    return result


# ==============================================================================
#  CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MLB Inference Engine -- Poisson + Skellam Model",
    )
    parser.add_argument("--team-a-name", default="New York Yankees")
    parser.add_argument("--team-b-name", default="Los Angeles Dodgers")
    parser.add_argument("--team-a-runs", type=float, default=None,
                        help="Team A avg runs scored per game")
    parser.add_argument("--team-b-runs", type=float, default=None,
                        help="Team B avg runs scored per game")
    parser.add_argument("--team-a-allowed", type=float, default=None,
                        help="Team A avg runs allowed per game")
    parser.add_argument("--team-b-allowed", type=float, default=None,
                        help="Team B avg runs allowed per game")
    parser.add_argument("--ou-line", type=float, default=None)
    parser.add_argument("--json-only", action="store_true",
                        help="Output only the JSON result")

    args = parser.parse_args()

    if args.team_a_runs and args.team_b_runs and args.team_a_allowed and args.team_b_allowed:
        team_a = TeamInput(args.team_a_name, args.team_a_runs, args.team_a_allowed, is_home=False)
        team_b = TeamInput(args.team_b_name, args.team_b_runs, args.team_b_allowed, is_home=True)
        result = predict_matchup(team_a, team_b, ou_line=args.ou_line)

        if args.json_only:
            print(result.to_json())
        else:
            print(result.to_json(indent=2))
    else:
        run_demo()


if __name__ == "__main__":
    main()
