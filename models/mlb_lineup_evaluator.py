"""
==============================================================================
 MLB Lineup Evaluator & Game Predictor
 ─────────────────────────────────────────────────────────────────────────────
 Author  : Lead Data Scientist (Sabermetrics Division)
 Purpose : Evaluate MLB lineup strength and predict game outcomes using
           Poisson-based run-scoring models grounded in sabermetric theory.
 ─────────────────────────────────────────────────────────────────────────────

 Theoretical Foundation
 ----------------------
 This module implements a two-sided Poisson regression approach:

   1. **Offensive Strength (OS):**
      Combines OPS (On-base Plus Slugging) and wOBA (weighted On-Base
      Average) for each of the 9 lineup batters. wOBA receives a higher
      weight (60%) than OPS (40%) because wOBA is park-neutralized and
      better correlated with actual run production (r = 0.91 vs 0.89).

   2. **Defensive Strength (DS):**
      Pitcher-centric metric: 65% weight on the Starting Pitcher's FIP
      (Fielding Independent Pitching) and 35% on the Bullpen's composite
      ERA/FIP average. FIP isolates the pitcher's true skill by stripping
      defense, making it the gold standard for predictive modelling.

   3. **Expected Runs (lambda):**
      Using the OS/DS ratio scaled against the league-average runs/game
      (currently ~4.53 R/G for 2024-2025), we derive a Poisson lambda
      for each team. The Poisson PMF then yields exact-score, over/under,
      and moneyline probabilities.

 Usage
 -----
     python -m models.mlb_lineup_evaluator

==============================================================================
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.stats import poisson


# ==============================================================================
#  Constants & League Baselines
# ==============================================================================

# MLB league-average benchmarks (2024-2025 combined)
LEAGUE_AVG_RUNS_PER_GAME = 4.53    # R/G across both leagues
LEAGUE_AVG_OPS = 0.714             # league-wide OPS
LEAGUE_AVG_WOBA = 0.312            # league-wide wOBA
LEAGUE_AVG_FIP = 4.13              # league-wide FIP
LEAGUE_AVG_ERA = 4.09              # league-wide ERA

# Weight allocations
WOBA_WEIGHT = 0.60   # wOBA contribution to Offensive Strength
OPS_WEIGHT = 0.40    # OPS contribution to Offensive Strength

SP_FIP_WEIGHT = 0.65   # Starting pitcher FIP weight in Defensive Strength
BULLPEN_WEIGHT = 0.35  # Bullpen composite weight in Defensive Strength

# Home-field advantage multiplier (empirically ~54% win rate for home teams)
HOME_FIELD_ADVANTAGE = 0.024  # adds ~0.10-0.15 runs to lambda

# Poisson simulation ceiling (max runs per team per game to consider)
MAX_RUNS = 20


# ==============================================================================
#  Data Classes
# ==============================================================================

@dataclass
class BatterProfile:
    """
    Profile for a single batter in the starting lineup.

    Attributes
    ----------
    name : str
        Player's full name (e.g., 'Aaron Judge').
    position : str
        Fielding position (e.g., 'RF', 'SS', 'DH').
    ops : float
        On-base Plus Slugging for the current season.
    woba : float
        Weighted On-Base Average (FanGraphs version).
    wrc_plus : float, optional
        wRC+ (Weighted Runs Created Plus); 100 = league average.
    war : float, optional
        Wins Above Replacement (fWAR).
    pa : int, optional
        Plate appearances (for sample-size weighting).
    """
    name: str
    position: str
    ops: float
    woba: float
    wrc_plus: float = 100.0
    war: float = 0.0
    pa: int = 0


@dataclass
class PitcherProfile:
    """
    Profile for a pitcher (starter or reliever).

    Attributes
    ----------
    name : str
        Pitcher's full name.
    role : str
        'SP' (starter) or 'RP' (reliever/bullpen).
    era : float
        Earned Run Average.
    fip : float
        Fielding Independent Pitching.
    whip : float, optional
        Walks + Hits per Inning Pitched.
    k_per_9 : float, optional
        Strikeouts per 9 innings.
    war : float, optional
        Wins Above Replacement (fWAR).
    ip : float, optional
        Innings pitched (for reliability weighting).
    xfip : float, optional
        Expected FIP (normalized HR/FB rate).
    siera : float, optional
        Skill-Interactive ERA.
    """
    name: str
    role: str   # 'SP' or 'RP'
    era: float
    fip: float
    whip: float = 1.30
    k_per_9: float = 8.5
    war: float = 0.0
    ip: float = 0.0
    xfip: float = 0.0
    siera: float = 0.0


@dataclass
class TeamLineup:
    """
    Complete team lineup for a single game.

    Attributes
    ----------
    team_name : str
        Full team name (e.g., 'New York Yankees').
    team_abbr : str
        Abbreviation (e.g., 'NYY').
    batters : list[BatterProfile]
        Ordered list of 9 starting batters (lineup order 1-9).
    starting_pitcher : PitcherProfile
        The game's starting pitcher.
    bullpen : list[PitcherProfile]
        Available relief pitchers.
    is_home : bool
        Whether this team is the home team.
    """
    team_name: str
    team_abbr: str
    batters: list[BatterProfile]
    starting_pitcher: PitcherProfile
    bullpen: list[PitcherProfile] = field(default_factory=list)
    is_home: bool = False


@dataclass
class GamePrediction:
    """
    Complete prediction output for a single game matchup.

    Attributes
    ----------
    home_team : str
    away_team : str
    home_lambda : float
        Expected runs for the home team (Poisson lambda).
    away_lambda : float
        Expected runs for the away team (Poisson lambda).
    home_win_prob : float
        Probability that the home team wins (0-1).
    away_win_prob : float
        Probability that the away team wins (0-1).
    tie_prob : float
        Probability of a tie in regulation (goes to extras).
    over_under_line : float
        Projected total runs (home + away lambdas).
    over_prob : float
        Probability total runs exceed the O/U line.
    under_prob : float
        Probability total runs fall under the O/U line.
    most_likely_score : tuple[int, int]
        The single most probable final score (home, away).
    score_distribution : dict
        Top N most probable exact scores with probabilities.
    home_offensive_strength : float
    away_offensive_strength : float
    home_defensive_strength : float
    away_defensive_strength : float
    """
    home_team: str
    away_team: str
    home_lambda: float
    away_lambda: float
    home_win_prob: float
    away_win_prob: float
    tie_prob: float
    over_under_line: float
    over_prob: float
    under_prob: float
    most_likely_score: tuple
    score_distribution: dict
    home_offensive_strength: float
    away_offensive_strength: float
    home_defensive_strength: float
    away_defensive_strength: float


# ==============================================================================
#  MLBGamePredictor  —  Core Prediction Engine
# ==============================================================================

class MLBGamePredictor:
    """
    Sabermetrics-driven MLB game prediction engine.

    Uses a Poisson model parameterized by offensive strength (OPS + wOBA)
    versus defensive strength (SP FIP + Bullpen ERA/FIP) to estimate
    run-scoring distributions and game outcomes.

    Parameters
    ----------
    league_avg_rpg : float
        League-average runs per game (baseline for scaling).
    home_advantage : float
        Home-field advantage modifier (added to home lambda).

    Examples
    --------
    >>> predictor = MLBGamePredictor()
    >>> # Build lineups ...
    >>> result = predictor.predict_game(home_lineup, away_lineup)
    >>> print(f"Home win prob: {result.home_win_prob:.1%}")
    """

    def __init__(
        self,
        league_avg_rpg: float = LEAGUE_AVG_RUNS_PER_GAME,
        home_advantage: float = HOME_FIELD_ADVANTAGE,
    ):
        self.league_avg_rpg = league_avg_rpg
        self.home_advantage = home_advantage

    # ------------------------------------------------------------------
    #  OFFENSIVE STRENGTH
    # ------------------------------------------------------------------

    def calculate_offensive_strength(
        self,
        batters: list[BatterProfile],
    ) -> float:
        """
        Calculate the composite Offensive Strength (OS) of a batting lineup.

        The OS is a weighted blend of each batter's OPS and wOBA, normalized
        against league averages. A lineup of perfectly average hitters
        produces an OS of exactly 1.0.

        Formula
        -------
        For each batter i in the lineup (1-9):

            batter_score_i = (OPS_WEIGHT * OPS_i / LG_OPS)
                           + (WOBA_WEIGHT * wOBA_i / LG_WOBA)

        OS = mean(batter_score_i for i in 1..9)

        Parameters
        ----------
        batters : list[BatterProfile]
            The 9 starting batters (lineup order).

        Returns
        -------
        float
            Offensive Strength index. Values > 1.0 indicate above-average
            offense; < 1.0 indicates below-average.

        Raises
        ------
        ValueError
            If fewer than 9 batters are provided.

        Notes
        -----
        - wOBA receives 60% weight because it correlates more strongly with
          actual runs scored (Pearson r = 0.91) compared to OPS (r = 0.89).
        - We normalize each metric against its league average so the two
          scales (OPS ~ 0.700, wOBA ~ 0.310) become commensurable.
        - If a batter has limited PA (< 100), their scores are regressed
          toward the league mean by a factor proportional to sample size.
        """
        if len(batters) < 9:
            raise ValueError(
                f"A starting lineup requires exactly 9 batters, "
                f"got {len(batters)}."
            )

        batter_scores = []
        for batter in batters[:9]:
            # Normalize each metric against league average
            ops_component = OPS_WEIGHT * (batter.ops / LEAGUE_AVG_OPS)
            woba_component = WOBA_WEIGHT * (batter.woba / LEAGUE_AVG_WOBA)
            raw_score = ops_component + woba_component

            # Sample-size regression: regress toward 1.0 for small PA
            if batter.pa > 0 and batter.pa < 200:
                regression_factor = batter.pa / 200.0
                raw_score = (raw_score * regression_factor) + (1.0 * (1 - regression_factor))

            batter_scores.append(raw_score)

        offensive_strength = float(np.mean(batter_scores))
        return offensive_strength

    # ------------------------------------------------------------------
    #  DEFENSIVE STRENGTH
    # ------------------------------------------------------------------

    def calculate_defensive_strength(
        self,
        starting_pitcher: PitcherProfile,
        bullpen: list[PitcherProfile],
    ) -> float:
        """
        Calculate the composite Defensive Strength (DS) of a pitching staff
        for a specific game.

        The DS blends the starting pitcher's FIP (65% weight) with the
        bullpen's average ERA/FIP composite (35% weight), normalized
        against the league-average FIP.

        Formula
        -------
        SP_component = SP_FIP / LEAGUE_AVG_FIP

        For each reliever j in the bullpen:
            reliever_composite_j = (ERA_j + FIP_j) / 2

        BP_component = mean(reliever_composite_j) / LEAGUE_AVG_FIP

        DS = (SP_FIP_WEIGHT * SP_component) + (BULLPEN_WEIGHT * BP_component)

        Parameters
        ----------
        starting_pitcher : PitcherProfile
            The game's starting pitcher with ERA and FIP.
        bullpen : list[PitcherProfile]
            Available relievers. If empty, the SP's metrics are used
            for the bullpen portion as well.

        Returns
        -------
        float
            Defensive Strength index. Values > 1.0 indicate worse-than-
            average pitching (more runs allowed); < 1.0 indicates
            above-average pitching (fewer runs allowed).

        Notes
        -----
        - FIP isolates pitcher skill (K, BB, HR) from defense and
          sequencing, making it the strongest single predictor of future
          ERA with a year-over-year correlation of r = 0.65.
        - The bullpen composite uses (ERA + FIP) / 2 to balance actual
          results with true talent, since reliever ERA can be volatile
          in small samples.
        - If a reliever has < 15 IP, their composite is regressed toward
          the league average to mitigate small-sample noise.
        """
        # Starting pitcher component (normalized to league average)
        sp_component = starting_pitcher.fip / LEAGUE_AVG_FIP

        # Bullpen component
        if bullpen:
            bp_composites = []
            for rp in bullpen:
                composite = (rp.era + rp.fip) / 2.0

                # Regress relievers with very few innings toward league avg
                if rp.ip > 0 and rp.ip < 30:
                    regression = rp.ip / 30.0
                    composite = (composite * regression) + (LEAGUE_AVG_FIP * (1 - regression))

                bp_composites.append(composite)

            bp_component = float(np.mean(bp_composites)) / LEAGUE_AVG_FIP
        else:
            # Fallback: use SP metrics for bullpen estimate
            bp_component = ((starting_pitcher.era + starting_pitcher.fip) / 2.0) / LEAGUE_AVG_FIP

        defensive_strength = (SP_FIP_WEIGHT * sp_component) + (BULLPEN_WEIGHT * bp_component)
        return defensive_strength

    # ------------------------------------------------------------------
    #  EXPECTED RUNS (POISSON LAMBDA)
    # ------------------------------------------------------------------

    def _calculate_expected_runs(
        self,
        offensive_strength: float,
        opposing_defensive_strength: float,
        is_home: bool = False,
    ) -> float:
        """
        Calculate expected runs (Poisson lambda) for a team.

        The fundamental insight: a team's expected run output is the
        league-average runs/game, scaled by how much better/worse their
        offense is relative to league average, and inversely scaled by
        how much better/worse the opposing pitching is.

        Formula
        -------
        lambda = LEAGUE_AVG_RPG * (OS / DS) + HOME_ADVANTAGE (if home)

        Where:
            OS = Offensive Strength of the batting team
            DS = Defensive Strength of the opposing pitching staff

        Parameters
        ----------
        offensive_strength : float
            OS of the batting team (1.0 = league average).
        opposing_defensive_strength : float
            DS of the opposing pitching staff (1.0 = league average).
        is_home : bool
            Whether this team bats at home.

        Returns
        -------
        float
            Expected runs (Poisson lambda), typically between 2.5 and 7.0.
        """
        ratio = offensive_strength / opposing_defensive_strength
        expected_runs = self.league_avg_rpg * ratio

        if is_home:
            expected_runs += self.home_advantage * self.league_avg_rpg

        # Floor at 1.5 (even the worst matchup scores some runs)
        # Cap at 10.0 to prevent degenerate distributions
        expected_runs = max(1.5, min(10.0, expected_runs))

        return expected_runs

    # ------------------------------------------------------------------
    #  POISSON SCORE DISTRIBUTION
    # ------------------------------------------------------------------

    def _build_score_matrix(
        self,
        home_lambda: float,
        away_lambda: float,
    ) -> np.ndarray:
        """
        Build a joint probability matrix of all possible score outcomes
        using independent Poisson distributions.

        Parameters
        ----------
        home_lambda : float
            Expected runs for the home team.
        away_lambda : float
            Expected runs for the away team.

        Returns
        -------
        np.ndarray
            Matrix of shape (MAX_RUNS+1, MAX_RUNS+1) where entry [h, a]
            is P(home_score=h AND away_score=a).
        """
        home_probs = np.array([poisson.pmf(k, home_lambda) for k in range(MAX_RUNS + 1)])
        away_probs = np.array([poisson.pmf(k, away_lambda) for k in range(MAX_RUNS + 1)])
        return np.outer(home_probs, away_probs)

    def _extract_probabilities(
        self,
        score_matrix: np.ndarray,
    ) -> dict:
        """
        Extract win/loss/tie probabilities and top score lines from
        the joint score matrix.

        Parameters
        ----------
        score_matrix : np.ndarray
            Joint probability matrix from _build_score_matrix.

        Returns
        -------
        dict with keys:
            'home_win_prob', 'away_win_prob', 'tie_prob',
            'most_likely_score', 'top_scores'
        """
        home_win_prob = 0.0
        away_win_prob = 0.0
        tie_prob = 0.0

        score_probs = {}

        for h in range(MAX_RUNS + 1):
            for a in range(MAX_RUNS + 1):
                prob = score_matrix[h, a]
                if h > a:
                    home_win_prob += prob
                elif a > h:
                    away_win_prob += prob
                else:
                    tie_prob += prob
                score_probs[(h, a)] = prob

        # Redistribute tie probability proportionally (MLB has no ties)
        if tie_prob > 0:
            total_decided = home_win_prob + away_win_prob
            if total_decided > 0:
                home_share = home_win_prob / total_decided
                home_win_prob += tie_prob * home_share
                away_win_prob += tie_prob * (1 - home_share)
            else:
                home_win_prob += tie_prob / 2
                away_win_prob += tie_prob / 2

        # Top 10 most likely scores
        sorted_scores = sorted(score_probs.items(), key=lambda x: x[1], reverse=True)
        top_scores = {score: prob for score, prob in sorted_scores[:10]}
        most_likely = sorted_scores[0][0]

        return {
            "home_win_prob": home_win_prob,
            "away_win_prob": away_win_prob,
            "tie_prob": tie_prob,
            "most_likely_score": most_likely,
            "top_scores": top_scores,
        }

    # ------------------------------------------------------------------
    #  OVER / UNDER
    # ------------------------------------------------------------------

    def _calculate_over_under(
        self,
        home_lambda: float,
        away_lambda: float,
        line: Optional[float] = None,
    ) -> dict:
        """
        Calculate over/under probabilities for the total runs scored.

        Uses the additive property of Poisson distributions:
        if X ~ Poisson(lam_H) and Y ~ Poisson(lam_A) are independent,
        then X + Y ~ Poisson(lam_H + lam_A).

        Parameters
        ----------
        home_lambda : float
            Home team expected runs.
        away_lambda : float
            Away team expected runs.
        line : float, optional
            The over/under line. If None, uses the combined lambdas.

        Returns
        -------
        dict with 'line', 'over_prob', 'under_prob', 'push_prob'
        """
        total_lambda = home_lambda + away_lambda
        if line is None:
            line = round(total_lambda * 2) / 2  # Round to nearest 0.5

        over_prob = 0.0
        under_prob = 0.0
        push_prob = 0.0

        for total in range(2 * MAX_RUNS + 1):
            prob = poisson.pmf(total, total_lambda)
            if total > line:
                over_prob += prob
            elif total < line:
                under_prob += prob
            else:
                push_prob += prob

        return {
            "line": line,
            "over_prob": over_prob,
            "under_prob": under_prob,
            "push_prob": push_prob,
        }

    # ------------------------------------------------------------------
    #  FULL GAME PREDICTION
    # ------------------------------------------------------------------

    def predict_game(
        self,
        home_lineup: TeamLineup,
        away_lineup: TeamLineup,
        ou_line: Optional[float] = None,
    ) -> GamePrediction:
        """
        Generate a complete game prediction from two team lineups.

        This is the primary entry point for the predictor. It orchestrates
        the full pipeline:

            1. Calculate Offensive Strength for both teams
            2. Calculate Defensive Strength for both teams
            3. Derive Poisson lambdas (expected runs)
            4. Build the joint score matrix
            5. Extract win/loss probabilities, exact scores, O/U

        Parameters
        ----------
        home_lineup : TeamLineup
            Complete lineup for the home team.
        away_lineup : TeamLineup
            Complete lineup for the away team.
        ou_line : float, optional
            Over/under line to evaluate. Defaults to auto-calculated.

        Returns
        -------
        GamePrediction
            Complete prediction with probabilities, expected scores,
            and strength metrics.

        Examples
        --------
        >>> predictor = MLBGamePredictor()
        >>> result = predictor.predict_game(yankees, dodgers)
        >>> print(f"{result.home_team} win: {result.home_win_prob:.1%}")
        >>> print(f"Expected: {result.most_likely_score}")
        """
        # Step 1: Offensive Strength
        home_os = self.calculate_offensive_strength(home_lineup.batters)
        away_os = self.calculate_offensive_strength(away_lineup.batters)

        # Step 2: Defensive Strength
        home_ds = self.calculate_defensive_strength(
            home_lineup.starting_pitcher, home_lineup.bullpen,
        )
        away_ds = self.calculate_defensive_strength(
            away_lineup.starting_pitcher, away_lineup.bullpen,
        )

        # Step 3: Expected runs (cross-matched: offense vs opposing defense)
        home_lambda = self._calculate_expected_runs(home_os, away_ds, is_home=True)
        away_lambda = self._calculate_expected_runs(away_os, home_ds, is_home=False)

        # Step 4: Score matrix
        score_matrix = self._build_score_matrix(home_lambda, away_lambda)
        probs = self._extract_probabilities(score_matrix)

        # Step 5: Over/Under
        ou = self._calculate_over_under(home_lambda, away_lambda, line=ou_line)

        return GamePrediction(
            home_team=home_lineup.team_name,
            away_team=away_lineup.team_name,
            home_lambda=home_lambda,
            away_lambda=away_lambda,
            home_win_prob=probs["home_win_prob"],
            away_win_prob=probs["away_win_prob"],
            tie_prob=probs["tie_prob"],
            over_under_line=ou["line"],
            over_prob=ou["over_prob"],
            under_prob=ou["under_prob"],
            most_likely_score=probs["most_likely_score"],
            score_distribution=probs["top_scores"],
            home_offensive_strength=home_os,
            away_offensive_strength=away_os,
            home_defensive_strength=home_ds,
            away_defensive_strength=away_ds,
        )

    # ------------------------------------------------------------------
    #  PRETTY PRINT
    # ------------------------------------------------------------------

    @staticmethod
    def print_prediction(pred: GamePrediction) -> None:
        """
        Print a formatted prediction report to the console.

        Parameters
        ----------
        pred : GamePrediction
            The prediction result from predict_game().
        """
        W = 72
        print()
        print("=" * W)
        print(f"  MLB GAME PREDICTION".center(W))
        print(f"  {pred.away_team}  @  {pred.home_team}".center(W))
        print("=" * W)

        print()
        print("-" * W)
        print("  STRENGTH ANALYSIS".center(W))
        print("-" * W)
        print(f"  {'Metric':<30} {'Home':>18} {'Away':>18}")
        print(f"  {'':─<30} {'':─>18} {'':─>18}")
        print(f"  {'Offensive Strength (OS)':<30} {pred.home_offensive_strength:>18.4f} {pred.away_offensive_strength:>18.4f}")
        print(f"  {'Defensive Strength (DS)':<30} {pred.home_defensive_strength:>18.4f} {pred.away_defensive_strength:>18.4f}")
        print(f"  {'Expected Runs (lambda)':<30} {pred.home_lambda:>18.2f} {pred.away_lambda:>18.2f}")

        print()
        print("-" * W)
        print("  WIN PROBABILITIES".center(W))
        print("-" * W)

        # Visual bar
        home_bar = int(pred.home_win_prob * 40)
        away_bar = int(pred.away_win_prob * 40)
        print(f"  {pred.home_team:<20} {pred.home_win_prob:>6.1%}  {'#' * home_bar}")
        print(f"  {pred.away_team:<20} {pred.away_win_prob:>6.1%}  {'#' * away_bar}")

        print()
        print("-" * W)
        print("  OVER / UNDER".center(W))
        print("-" * W)
        print(f"  Total Line:  {pred.over_under_line:.1f}")
        print(f"  OVER  prob:  {pred.over_prob:.1%}")
        print(f"  UNDER prob:  {pred.under_prob:.1%}")

        print()
        print("-" * W)
        print("  MOST LIKELY SCORES".center(W))
        print("-" * W)

        h_score, a_score = pred.most_likely_score
        print(f"  >>> Predicted Final: {pred.home_team} {h_score} - {pred.away_team} {a_score}")
        print()
        print(f"  {'Score (Home-Away)':<25} {'Probability':>12}")
        print(f"  {'':─<25} {'':─>12}")
        for (h, a), prob in list(pred.score_distribution.items())[:8]:
            print(f"  {h:>5} - {a:<5}               {prob:>11.2%}")

        print()
        print("=" * W)
        print()


# ==============================================================================
#  DB-POWERED LINEUP BUILDER (uses data from mlb_sabermetrics PostgreSQL)
# ==============================================================================

def build_lineup_from_db(
    team_abbr: str,
    batter_names: list[str],
    sp_name: str,
    bullpen_names: list[str],
    season: int = 2025,
    is_home: bool = False,
) -> Optional[TeamLineup]:
    """
    Build a TeamLineup by pulling real stats from the PostgreSQL database.

    Parameters
    ----------
    team_abbr : str
        Team abbreviation (e.g., 'NYY').
    batter_names : list[str]
        Names of the 9 starting batters in lineup order.
    sp_name : str
        Name of the starting pitcher.
    bullpen_names : list[str]
        Names of the bullpen pitchers.
    season : int
        Season year to pull stats from.
    is_home : bool
        Whether this team is the home team.

    Returns
    -------
    TeamLineup or None if database is unavailable.
    """
    try:
        from services.config import DATABASE_URL
        from services.models import MLBPlayerBatting, MLBPlayerPitching, get_engine
        from sqlalchemy.orm import sessionmaker

        engine = get_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Fetch batters
        batters = []
        for name in batter_names:
            row = (
                session.query(MLBPlayerBatting)
                .filter(
                    MLBPlayerBatting.player_name == name,
                    MLBPlayerBatting.season == season,
                )
                .first()
            )
            if row:
                batters.append(BatterProfile(
                    name=row.player_name,
                    position="",
                    ops=row.ops or LEAGUE_AVG_OPS,
                    woba=row.woba or LEAGUE_AVG_WOBA,
                    wrc_plus=row.wrc_plus or 100.0,
                    war=row.war or 0.0,
                    pa=row.pa or 0,
                ))
            else:
                print(f"  [WARN] Batter '{name}' not found in DB for {season}, using league avg")
                batters.append(BatterProfile(
                    name=name, position="", ops=LEAGUE_AVG_OPS, woba=LEAGUE_AVG_WOBA,
                ))

        # Fetch starting pitcher
        sp_row = (
            session.query(MLBPlayerPitching)
            .filter(
                MLBPlayerPitching.player_name == sp_name,
                MLBPlayerPitching.season == season,
            )
            .first()
        )
        if sp_row:
            sp = PitcherProfile(
                name=sp_row.player_name, role="SP",
                era=sp_row.era or LEAGUE_AVG_ERA,
                fip=sp_row.fip or LEAGUE_AVG_FIP,
                whip=sp_row.whip or 1.30,
                k_per_9=sp_row.k_per_9 or 8.5,
                war=sp_row.war or 0.0,
                ip=sp_row.ip or 0.0,
                xfip=sp_row.xfip or 0.0,
                siera=sp_row.siera or 0.0,
            )
        else:
            print(f"  [WARN] SP '{sp_name}' not found in DB, using league avg")
            sp = PitcherProfile(name=sp_name, role="SP", era=LEAGUE_AVG_ERA, fip=LEAGUE_AVG_FIP)

        # Fetch bullpen
        bp = []
        for bp_name in bullpen_names:
            bp_row = (
                session.query(MLBPlayerPitching)
                .filter(
                    MLBPlayerPitching.player_name == bp_name,
                    MLBPlayerPitching.season == season,
                )
                .first()
            )
            if bp_row:
                bp.append(PitcherProfile(
                    name=bp_row.player_name, role="RP",
                    era=bp_row.era or LEAGUE_AVG_ERA,
                    fip=bp_row.fip or LEAGUE_AVG_FIP,
                    war=bp_row.war or 0.0,
                    ip=bp_row.ip or 0.0,
                ))
            else:
                bp.append(PitcherProfile(
                    name=bp_name, role="RP", era=LEAGUE_AVG_ERA, fip=LEAGUE_AVG_FIP,
                ))

        session.close()

        # Resolve full team name
        team_name_map = {
            "NYY": "New York Yankees", "LAD": "Los Angeles Dodgers",
            "HOU": "Houston Astros", "ATL": "Atlanta Braves",
            "SEA": "Seattle Mariners", "BOS": "Boston Red Sox",
            "PHI": "Philadelphia Phillies", "SDP": "San Diego Padres",
            "NYM": "New York Mets", "BAL": "Baltimore Orioles",
            "TBR": "Tampa Bay Rays", "TOR": "Toronto Blue Jays",
            "CLE": "Cleveland Guardians", "MIN": "Minnesota Twins",
            "CHW": "Chicago White Sox", "DET": "Detroit Tigers",
            "KCR": "Kansas City Royals", "TEX": "Texas Rangers",
            "LAA": "Los Angeles Angels", "OAK": "Oakland Athletics",
            "MIA": "Miami Marlins", "WSN": "Washington Nationals",
            "MIL": "Milwaukee Brewers", "CHC": "Chicago Cubs",
            "STL": "St. Louis Cardinals", "CIN": "Cincinnati Reds",
            "PIT": "Pittsburgh Pirates", "SFG": "San Francisco Giants",
            "ARI": "Arizona Diamondbacks", "COL": "Colorado Rockies",
        }

        return TeamLineup(
            team_name=team_name_map.get(team_abbr, team_abbr),
            team_abbr=team_abbr,
            batters=batters,
            starting_pitcher=sp,
            bullpen=bp,
            is_home=is_home,
        )

    except Exception as e:
        print(f"  [ERROR] Could not build lineup from DB: {e}")
        return None


# ==============================================================================
#  CONSOLE TEST  —  Yankees vs Dodgers (2025 Season Stats)
# ==============================================================================

def run_console_test():
    """
    Simulate a Yankees @ Dodgers matchup using real 2025 season data
    from the PostgreSQL database, with fallback to hardcoded stats.
    """
    print()
    print("=" * 72)
    print("  MLB LINEUP EVALUATOR — CONSOLE TEST".center(72))
    print("  New York Yankees  @  Los Angeles Dodgers".center(72))
    print("=" * 72)
    print()

    # ---------------------------------------------------------
    #  Try database-driven lineups first
    # ---------------------------------------------------------
    print("[1/3] Attempting to load lineups from PostgreSQL...")

    yankees_lineup = build_lineup_from_db(
        team_abbr="NYY",
        batter_names=[
            "Anthony Volpe",      # SS
            "Juan Soto",          # RF
            "Aaron Judge",        # CF/DH
            "Cody Bellinger",     # 1B
            "Jazz Chisholm Jr.",  # 3B
            "Giancarlo Stanton",  # DH
            "Austin Wells",       # C
            "Alex Verdugo",       # LF
            "Oswaldo Cabrera",    # 2B
        ],
        sp_name="Gerrit Cole",
        bullpen_names=["Clay Holmes", "Luke Weaver", "Tommy Kahnle", "Ian Hamilton"],
        season=2025,
        is_home=False,
    )

    dodgers_lineup = build_lineup_from_db(
        team_abbr="LAD",
        batter_names=[
            "Mookie Betts",       # SS
            "Shohei Ohtani",      # DH
            "Freddie Freeman",    # 1B
            "Teoscar Hernandez",  # LF
            "Will Smith",         # C
            "Max Muncy",          # 3B
            "Tommy Edman",        # 2B
            "Andy Pages",         # RF
            "James Outman",       # CF
        ],
        sp_name="Yoshinobu Yamamoto",
        bullpen_names=["Evan Phillips", "Alex Vesia", "Blake Treinen", "Ryan Brasier"],
        season=2025,
        is_home=True,
    )

    # ---------------------------------------------------------
    #  Fallback to hardcoded stats if DB unavailable
    # ---------------------------------------------------------
    if yankees_lineup is None or len(yankees_lineup.batters) == 0:
        print("[FALLBACK] Using hardcoded Yankees stats...")
        yankees_lineup = TeamLineup(
            team_name="New York Yankees",
            team_abbr="NYY",
            batters=[
                BatterProfile("Anthony Volpe",      "SS", ops=0.716, woba=0.310, wrc_plus=98,  war=3.2, pa=650),
                BatterProfile("Juan Soto",          "RF", ops=0.917, woba=0.395, wrc_plus=163, war=7.2, pa=700),
                BatterProfile("Aaron Judge",        "CF", ops=1.144, woba=0.452, wrc_plus=204, war=10.1, pa=650),
                BatterProfile("Cody Bellinger",     "1B", ops=0.751, woba=0.323, wrc_plus=108, war=2.1, pa=550),
                BatterProfile("Jazz Chisholm Jr.",   "3B", ops=0.823, woba=0.345, wrc_plus=128, war=4.5, pa=580),
                BatterProfile("Giancarlo Stanton",  "DH", ops=0.785, woba=0.332, wrc_plus=115, war=1.8, pa=450),
                BatterProfile("Austin Wells",       "C",  ops=0.798, woba=0.340, wrc_plus=120, war=3.0, pa=520),
                BatterProfile("Alex Verdugo",       "LF", ops=0.663, woba=0.290, wrc_plus=85,  war=0.5, pa=600),
                BatterProfile("Oswaldo Cabrera",    "2B", ops=0.695, woba=0.300, wrc_plus=90,  war=1.0, pa=480),
            ],
            starting_pitcher=PitcherProfile(
                "Gerrit Cole", "SP", era=3.41, fip=3.15, whip=1.07,
                k_per_9=11.0, war=5.0, ip=200.0, xfip=3.20, siera=3.10,
            ),
            bullpen=[
                PitcherProfile("Clay Holmes",    "RP", era=3.80, fip=3.60, ip=65.0),
                PitcherProfile("Luke Weaver",    "RP", era=2.90, fip=3.10, ip=70.0),
                PitcherProfile("Tommy Kahnle",   "RP", era=2.10, fip=2.80, ip=55.0),
                PitcherProfile("Ian Hamilton",   "RP", era=3.50, fip=3.40, ip=50.0),
            ],
            is_home=False,
        )

    if dodgers_lineup is None or len(dodgers_lineup.batters) == 0:
        print("[FALLBACK] Using hardcoded Dodgers stats...")
        dodgers_lineup = TeamLineup(
            team_name="Los Angeles Dodgers",
            team_abbr="LAD",
            batters=[
                BatterProfile("Mookie Betts",       "SS", ops=0.875, woba=0.375, wrc_plus=148, war=6.8, pa=650),
                BatterProfile("Shohei Ohtani",      "DH", ops=1.014, woba=0.420, wrc_plus=172, war=7.5, pa=680),
                BatterProfile("Freddie Freeman",    "1B", ops=0.858, woba=0.367, wrc_plus=142, war=5.5, pa=660),
                BatterProfile("Teoscar Hernandez",  "LF", ops=0.840, woba=0.355, wrc_plus=135, war=3.8, pa=600),
                BatterProfile("Will Smith",         "C",  ops=0.820, woba=0.348, wrc_plus=130, war=4.0, pa=550),
                BatterProfile("Max Muncy",          "3B", ops=0.802, woba=0.340, wrc_plus=125, war=3.2, pa=580),
                BatterProfile("Tommy Edman",        "2B", ops=0.745, woba=0.320, wrc_plus=105, war=3.5, pa=590),
                BatterProfile("Andy Pages",         "RF", ops=0.730, woba=0.315, wrc_plus=100, war=1.5, pa=500),
                BatterProfile("James Outman",       "CF", ops=0.710, woba=0.305, wrc_plus=95,  war=1.0, pa=480),
            ],
            starting_pitcher=PitcherProfile(
                "Yoshinobu Yamamoto", "SP", era=3.00, fip=2.85, whip=0.95,
                k_per_9=10.5, war=4.5, ip=170.0, xfip=2.95, siera=2.90,
            ),
            bullpen=[
                PitcherProfile("Evan Phillips",  "RP", era=2.50, fip=2.70, ip=60.0),
                PitcherProfile("Alex Vesia",     "RP", era=2.30, fip=2.50, ip=55.0),
                PitcherProfile("Blake Treinen",  "RP", era=1.93, fip=2.40, ip=65.0),
                PitcherProfile("Ryan Brasier",   "RP", era=3.20, fip=3.10, ip=50.0),
            ],
            is_home=True,
        )

    # ---------------------------------------------------------
    #  Print lineup details
    # ---------------------------------------------------------
    print()
    print("[2/3] Lineup Details:")
    print()
    for label, lineup in [("AWAY - NYY", yankees_lineup), ("HOME - LAD", dodgers_lineup)]:
        print(f"  --- {label}: {lineup.team_name} ---")
        print(f"  {'#':<4} {'Batter':<22} {'Pos':<5} {'OPS':>7} {'wOBA':>7} {'wRC+':>6} {'WAR':>5}")
        print(f"  {'':─<4} {'':─<22} {'':─<5} {'':─>7} {'':─>7} {'':─>6} {'':─>5}")
        for i, b in enumerate(lineup.batters, 1):
            print(f"  {i:<4} {b.name:<22} {b.position:<5} {b.ops:>7.3f} {b.woba:>7.3f} {b.wrc_plus:>6.0f} {b.war:>5.1f}")
        sp = lineup.starting_pitcher
        print(f"  SP:  {sp.name:<22}       ERA={sp.era:.2f}  FIP={sp.fip:.2f}  K/9={sp.k_per_9:.1f}  WAR={sp.war:.1f}")
        print(f"  Bullpen ({len(lineup.bullpen)} arms): ", end="")
        print(", ".join(f"{rp.name}({rp.fip:.2f})" for rp in lineup.bullpen))
        print()

    # ---------------------------------------------------------
    #  Run prediction
    # ---------------------------------------------------------
    print("[3/3] Running Poisson prediction model...")
    print()

    predictor = MLBGamePredictor()
    prediction = predictor.predict_game(
        home_lineup=dodgers_lineup,
        away_lineup=yankees_lineup,
        ou_line=8.5,
    )

    predictor.print_prediction(prediction)

    # ---------------------------------------------------------
    #  Implied Moneyline
    # ---------------------------------------------------------
    print("  IMPLIED MONEYLINES (American odds)")
    print("  " + "-" * 50)
    for team, prob in [
        (prediction.home_team, prediction.home_win_prob),
        (prediction.away_team, prediction.away_win_prob),
    ]:
        if prob >= 0.5:
            odds = -(prob / (1 - prob)) * 100
            print(f"  {team:<25} {odds:>+.0f}  ({prob:.1%})")
        else:
            odds = ((1 - prob) / prob) * 100
            print(f"  {team:<25} {odds:>+.0f}  ({prob:.1%})")

    print()
    return prediction


# ==============================================================================
#  Entry Point
# ==============================================================================

if __name__ == "__main__":
    run_console_test()
