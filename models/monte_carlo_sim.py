"""
==============================================================================
 MLB Monte Carlo Simulation Engine
 ==============================================================================
 Author  : Senior Simulation Engineer
 Module  : models/monte_carlo_sim.py
 ==============================================================================

 DESCRIPTION
 -----------
 This module implements an inning-by-inning Monte Carlo simulation (10,000+ 
 iterations) to complement the static Skellam/Poisson models. 

 Key Features:
 1. Sabermetric Variance: Introduces random variance based on player/team 
    historical standard deviation.
 2. Bullpen Fatigue Factor: If a team's bullpen has worked > 5 innings in the
    last 2 days, their defensive effectiveness (run prevention) drops by 15% 
    in the late innings (7th, 8th, and 9th).
 3. Volatility Alert: Compares the simulated Win Probability with the 
    analytical Skellam Probability. Discrepancies > 5% trigger a High 
    Volatility Alert.

 Usage
 -----
     python -m models.monte_carlo_sim
==============================================================================
"""

import argparse
import math
import numpy as np
from dataclasses import dataclass
from typing import Dict, Tuple

# Re-use analytical models for comparison
from models.mlb_engine import adjust_lambda, get_moneyline_probability


# ==============================================================================
#  Data Structures
# ==============================================================================

@dataclass
class TeamSimProfile:
    """
    Simulation profile for a team.
    
    Attributes
    ----------
    name : str
        Team name.
    avg_runs_scored : float
        Season average runs scored per game.
    avg_runs_allowed : float
        Season average runs allowed per game.
    sabermetric_variance : float
        Standard deviation multiplier based on lineup consistency.
        (E.g., 1.0 = normal, 1.2 = high volatility team like Yankees).
    bullpen_fatigued : bool
        True if bullpen pitched > 5 IP in last 2 days.
    is_home : bool
        Whether this team plays at home (bats in bottom of inning).
    """
    name: str
    avg_runs_scored: float
    avg_runs_allowed: float
    sabermetric_variance: float = 1.0
    bullpen_fatigued: bool = False
    is_home: bool = False


@dataclass
class SimResult:
    """
    Result of the Monte Carlo Simulation.
    """
    team_a_wins: int
    team_b_wins: int
    ties: int  # Extra innings typically resolve, but we track regulation ties
    total_sims: int
    team_a_avg_runs: float
    team_b_avg_runs: float
    win_prob_a: float
    win_prob_b: float
    skellam_prob_a: float
    volatility_alert: bool
    discrepancy: float


# ==============================================================================
#  SIMULATION ENGINE
# ==============================================================================

class MLBMonteCarlo:
    """
    Inning-by-Inning Monte Carlo Simulator.
    """

    def __init__(self, iterations: int = 10000):
        self.iterations = iterations
        self.innings = 9
    
    def simulate_inning_runs(self, expected_inning_runs: float, variance: float) -> int:
        """
        Simulate runs scored in a single inning using a Gamma-Poisson mixture 
        to model overdispersion (Sabermetric Variance).
        
        Using a standard Poisson doesn't capture the "clumpiness" of baseball
        scoring. We use Negative Binomial (Gamma-Poisson) where the variance
        can be tuned.
        """
        # If variance is 1.0, it acts close to Poisson.
        # Higher variance stretches the distribution.
        if expected_inning_runs <= 0:
            return 0
            
        # Gamma shape and scale parameters
        # mean = shape * scale = expected_inning_runs
        # var = mean * variance = shape * scale^2
        # Therefore: scale = variance, shape = expected_inning_runs / variance
        
        # Enforce minimum variance bounds to avoid math domain errors
        effective_variance = max(1.01, variance) 
        
        scale = effective_variance - 1.0
        shape = expected_inning_runs / scale
        
        # Sample lambda from Gamma, then Poisson from that lambda
        simulated_lambda = np.random.gamma(shape, scale)
        runs = np.random.poisson(simulated_lambda)
        return int(runs)

    def run_simulation(self, team_a: TeamSimProfile, team_b: TeamSimProfile) -> SimResult:
        """
        Run the Monte Carlo simulation 10,000 times.
        """
        # 1. Base lambdas (runs per game) adjusted by opponent
        base_lambda_a = adjust_lambda(team_a.avg_runs_scored, team_b.avg_runs_allowed, is_home=team_a.is_home)
        base_lambda_b = adjust_lambda(team_b.avg_runs_scored, team_a.avg_runs_allowed, is_home=team_b.is_home)

        # Expected runs per inning (base)
        inning_lambda_a = base_lambda_a / self.innings
        inning_lambda_b = base_lambda_b / self.innings

        team_a_wins = 0
        team_b_wins = 0
        total_runs_a = 0
        total_runs_b = 0

        # Run vectorized or loop simulation
        # Using loop for clarity on inning-by-inning fatigue rules
        for _ in range(self.iterations):
            score_a = 0
            score_b = 0

            for inning in range(1, self.innings + 1):
                # Apply Bullpen Fatigue (defense reduction = offensive boost for opponent)
                # Innings 7, 8, 9
                late_inning = (inning >= 7)
                
                # If B's bullpen is fatigued, A scores more in late innings
                current_lambda_a = inning_lambda_a
                if late_inning and team_b.bullpen_fatigued:
                    current_lambda_a *= 1.15  # +15% boost to offense A (15% drop in defense B)
                
                # If A's bullpen is fatigued, B scores more in late innings
                current_lambda_b = inning_lambda_b
                if late_inning and team_a.bullpen_fatigued:
                    current_lambda_b *= 1.15

                # Simulate half-innings
                runs_a = self.simulate_inning_runs(current_lambda_a, team_a.sabermetric_variance)
                runs_b = self.simulate_inning_runs(current_lambda_b, team_b.sabermetric_variance)

                score_a += runs_a
                
                # Bottom of the 9th logic: if Home team is winning, they don't bat.
                if inning == self.innings and team_b.is_home and score_b > score_a:
                    break # Walk-off / Game over
                
                score_b += runs_b
                
                # Extra innings logic (simplified sudden death resolution for stat gathering)
                if inning == self.innings and score_a == score_b:
                    # Resolve tie in extras (50/50 proxy or skill-based)
                    # To keep it rigorous, we add a 10th inning simulation difference
                    ex_a = self.simulate_inning_runs(inning_lambda_a, team_a.sabermetric_variance)
                    ex_b = self.simulate_inning_runs(inning_lambda_b, team_b.sabermetric_variance)
                    # Force resolution
                    while ex_a == ex_b:
                        ex_a = self.simulate_inning_runs(inning_lambda_a, team_a.sabermetric_variance)
                        ex_b = self.simulate_inning_runs(inning_lambda_b, team_b.sabermetric_variance)
                    score_a += ex_a
                    score_b += ex_b

            # Tally game result
            if score_a > score_b:
                team_a_wins += 1
            elif score_b > score_a:
                team_b_wins += 1

            total_runs_a += score_a
            total_runs_b += score_b

        # Win Probabilities
        win_prob_a = team_a_wins / self.iterations
        win_prob_b = team_b_wins / self.iterations

        # 2. Analytical Comparison (Skellam)
        analytical = get_moneyline_probability(base_lambda_a, base_lambda_b)
        skellam_prob_a = analytical["team_a_win_prob"]

        # 3. Volatility Alert
        discrepancy = abs(win_prob_a - skellam_prob_a)
        volatility_alert = discrepancy > 0.05  # >5%

        return SimResult(
            team_a_wins=team_a_wins,
            team_b_wins=team_b_wins,
            ties=0, # Resolved by extras
            total_sims=self.iterations,
            team_a_avg_runs=(total_runs_a / self.iterations),
            team_b_avg_runs=(total_runs_b / self.iterations),
            win_prob_a=win_prob_a,
            win_prob_b=win_prob_b,
            skellam_prob_a=skellam_prob_a,
            volatility_alert=volatility_alert,
            discrepancy=discrepancy
        )


# ==============================================================================
#  CONSOLE EXECUTION
# ==============================================================================

def print_results(team_a: TeamSimProfile, team_b: TeamSimProfile, result: SimResult):
    """
    Format and print the Monte Carlo simulation results.
    """
    W = 72
    print()
    print("=" * W)
    print("  MONTE CARLO SIMULATION RESULTS (10,000 Iterations)".center(W))
    print("=" * W)
    print()

    print(f"  MATCHUP:")
    print(f"    (Away) {team_a.name:<20} | Var: {team_a.sabermetric_variance:.2f} | Bullpen Fatigued: {team_a.bullpen_fatigued}")
    print(f"    (Home) {team_b.name:<20} | Var: {team_b.sabermetric_variance:.2f} | Bullpen Fatigued: {team_b.bullpen_fatigued}")
    print("-" * W)
    
    print(f"  SIMULATED AVERAGES:")
    print(f"    {team_a.name}: {result.team_a_avg_runs:.2f} Runs/Game")
    print(f"    {team_b.name}: {result.team_b_avg_runs:.2f} Runs/Game")
    print("-" * W)

    print(f"  MONTE CARLO WIN PROBABILITY:")
    bar_a = "#" * int(result.win_prob_a * 40)
    bar_b = "#" * int(result.win_prob_b * 40)
    print(f"    {team_a.name[:15]:<16} {result.win_prob_a*100:>6.2f}%  [{bar_a}]")
    print(f"    {team_b.name[:15]:<16} {result.win_prob_b*100:>6.2f}%  [{bar_b}]")
    print("-" * W)

    print(f"  ANALYTICAL SKELLAM PROBABILITY:")
    print(f"    {team_a.name[:15]:<16} {result.skellam_prob_a*100:>6.2f}% (Static Baseline)")
    print("-" * W)

    print(f"  VOLATILITY METRICS:")
    print(f"    Absolute Discrepancy: {result.discrepancy*100:.2f}%")
    
    if result.volatility_alert:
        print()
        print("    [!] 🚨 ALERTA DE ALTA VOLATILIDAD 🚨 [!]")
        print("        La simulación difiere significativamente del modelo base (>5%).")
        print("        Motivo probable: Fatiga extrema de bullpen combinada con alta.")
        print("        varianza sabermétrica en la alineación genera un entorno caótico.")
        print("        Recomendación: Evitar apuestas de línea de dinero directas; evaluar Over/Under.")
    else:
        print()
        print("    [+] Modelo Estable. La simulación converge con las matemáticas de Skellam.")
    
    print("=" * W)
    print()


def run_demo():
    """
    Demo: Yankees vs Dodgers with a fatigued Dodgers bullpen and extreme Yankees variance.
    """
    # Create Team A (Yankees)
    yankees = TeamSimProfile(
        name="New York Yankees",
        avg_runs_scored=5.12,
        avg_runs_allowed=3.98,
        sabermetric_variance=1.45,   # High variance (Judge/Soto boom or bust)
        bullpen_fatigued=False,      # Rested bullpen
        is_home=False
    )

    # Create Team B (Dodgers)
    dodgers = TeamSimProfile(
        name="Los Angeles Dodgers",
        avg_runs_scored=4.87,
        avg_runs_allowed=3.65,
        sabermetric_variance=1.10,   # More consistent
        bullpen_fatigued=True,       # CRITICAL FACTOR: >5 innings in last 2 days
        is_home=True
    )

    print("[SYSTEM] Initializes Monte Carlo Engine...")
    engine = MLBMonteCarlo(iterations=10000)
    print("[SYSTEM] Simulating 10,000 games with Sabermetric Variance and Bullpen Decay...")
    result = engine.run_simulation(yankees, dodgers)
    
    print_results(yankees, dodgers, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10000)
    args = parser.parse_args()
    run_demo()
