"""
=============================================================================
 MLB Sabermetrics — Data Ingestion Pipeline  (ETL)
 ─────────────────────────────────────────────────────────────────────────────
 Author  : Senior Data Engineer (Sabermetrics)
 Stack   : pybaseball → pandas (Transform) → SQLAlchemy + PostgreSQL (Load)
 ─────────────────────────────────────────────────────────────────────────────
 Usage:
     python -m services.mlb_data_pipeline              # current season
     python -m services.mlb_data_pipeline --season 2025
     python -m services.mlb_data_pipeline --season 2025 --skip-standings
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

# ── pybaseball ──────────────────────────────────────────────────────────────
import pybaseball
from pybaseball import batting_stats, pitching_stats, standings, schedule_and_record

# Disable pybaseball's internal cache warning noise
pybaseball.cache.enable()

# ── Internal modules ────────────────────────────────────────────────────────
from services.config import (
    BULK_INSERT_CHUNK,
    DATABASE_URL,
    DEFAULT_SEASON,
    LOG_LEVEL,
    MIN_IP,
    MIN_PA,
)
from services.models import (
    Base,
    MLBGameLog,
    MLBPlayerBatting,
    MLBPlayerPitching,
    MLBTeam,
    get_engine,
    get_session,
    init_db,
)

# ──────────────────────────────────────────────────────────────────────────────
#  Logging setup
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mlb_pipeline")


# ═══════════════════════════════════════════════════════════════════════════════
#  COLUMN MAPPING — pybaseball DataFrame → SQLAlchemy model fields
# ═══════════════════════════════════════════════════════════════════════════════

BATTING_COL_MAP = {
    "Name": "player_name",
    "IDfg": "player_id",
    "Team": "team",
    "Season": "season",
    "Age": "age",
    "G": "games",
    "PA": "pa",
    "AB": "ab",
    "H": "hits",
    "2B": "doubles",
    "3B": "triples",
    "HR": "hr",
    "RBI": "rbi",
    "R": "runs",
    "SB": "sb",
    "CS": "cs",
    "BB": "bb",
    "SO": "so",
    "HBP": "hbp",
    "AVG": "avg",
    "OBP": "obp",
    "SLG": "slg",
    "OPS": "ops",
    "ISO": "iso",
    "WAR": "war",
    "wRC+": "wrc_plus",
    "wOBA": "woba",
    "BABIP": "babip",
    "Off": "off",
    "Def": "defense",
    "BsR": "bsr",
    "GB%": "gb_pct",
    "FB%": "fb_pct",
    "LD%": "ld_pct",
    "HR/FB": "hr_fb",
    "Hard%": "hard_hit_pct",
    "Barrel%": "barrel_pct",
}

PITCHING_COL_MAP = {
    "Name": "player_name",
    "IDfg": "player_id",
    "Team": "team",
    "Season": "season",
    "Age": "age",
    "W": "wins",
    "L": "losses",
    "ERA": "era",
    "G": "games",
    "GS": "games_started",
    "SV": "saves",
    "IP": "ip",
    "H": "hits_allowed",
    "R": "runs_allowed",
    "ER": "er",
    "HR": "hr_allowed",
    "BB": "bb",
    "SO": "so",
    "HBP": "hbp",
    "WHIP": "whip",
    "K/9": "k_per_9",
    "BB/9": "bb_per_9",
    "HR/9": "hr_per_9",
    "K/BB": "k_bb_ratio",
    "K%": "k_pct",
    "BB%": "bb_pct",
    "WAR": "war",
    "FIP": "fip",
    "xFIP": "xfip",
    "SIERA": "siera",
    "LOB%": "lob_pct",
    "GB%": "gb_pct",
    "FB%": "fb_pct",
    "HR/FB": "hr_fb",
    "BABIP": "babip",
    "Hard%": "hard_hit_pct",
    "Barrel%": "barrel_pct",
}

# Team abbreviation → full name helper (for standings)
TEAM_ABBR_MAP = {
    "NYY": "New York Yankees", "BOS": "Boston Red Sox",
    "TBR": "Tampa Bay Rays", "TOR": "Toronto Blue Jays",
    "BAL": "Baltimore Orioles", "CLE": "Cleveland Guardians",
    "MIN": "Minnesota Twins", "CHW": "Chicago White Sox",
    "DET": "Detroit Tigers", "KCR": "Kansas City Royals",
    "HOU": "Houston Astros", "SEA": "Seattle Mariners",
    "TEX": "Texas Rangers", "LAA": "Los Angeles Angels",
    "OAK": "Oakland Athletics", "ATL": "Atlanta Braves",
    "NYM": "New York Mets", "PHI": "Philadelphia Phillies",
    "MIA": "Miami Marlins", "WSN": "Washington Nationals",
    "MIL": "Milwaukee Brewers", "CHC": "Chicago Cubs",
    "STL": "St. Louis Cardinals", "CIN": "Cincinnati Reds",
    "PIT": "Pittsburgh Pirates", "LAD": "Los Angeles Dodgers",
    "SDP": "San Diego Padres", "SFG": "San Francisco Giants",
    "ARI": "Arizona Diamondbacks", "COL": "Colorado Rockies",
}

# Divisions (by first table index from pybaseball.standings)
DIVISION_ORDER = [
    ("AL", "East"), ("AL", "Central"), ("AL", "West"),
    ("NL", "East"), ("NL", "Central"), ("NL", "West"),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  EXTRACT  — pull raw DataFrames from pybaseball
# ═══════════════════════════════════════════════════════════════════════════════

def extract_standings(season: int) -> pd.DataFrame:
    """Fetch division standings and unify into a single DataFrame."""
    logger.info(f"[EXTRACT] Extracting standings for {season} ...")
    try:
        tables = standings(season)
    except Exception as e:
        logger.warning(f"[WARN] Could not fetch standings: {e}")
        return pd.DataFrame()

    frames = []
    for idx, df in enumerate(tables):
        if idx >= len(DIVISION_ORDER):
            break
        league, division = DIVISION_ORDER[idx]
        df = df.copy()
        df["league"] = league
        df["division"] = division
        df["season"] = season
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"   -> {len(combined)} team rows extracted.")
    return combined


def extract_batting(season: int) -> pd.DataFrame:
    """Fetch FanGraphs qualified batting stats for the season."""
    logger.info(f"[EXTRACT] Extracting batting stats for {season} ...")
    try:
        df = batting_stats(season, qual=MIN_PA)
        logger.info(f"   -> {len(df)} batter rows extracted.")
        return df
    except Exception as e:
        logger.error(f"[FAIL] Batting extraction failed: {e}")
        return pd.DataFrame()


def extract_pitching(season: int) -> pd.DataFrame:
    """Fetch FanGraphs qualified pitching stats for the season."""
    logger.info(f"[EXTRACT] Extracting pitching stats for {season} ...")
    try:
        df = pitching_stats(season, qual=MIN_IP)
        logger.info(f"   -> {len(df)} pitcher rows extracted.")
        return df
    except Exception as e:
        logger.error(f"[FAIL] Pitching extraction failed: {e}")
        return pd.DataFrame()


def extract_game_logs(season: int) -> pd.DataFrame:
    """
    Build game log from each team's schedule_and_record.
    De‑duplicated so each game appears once (home team's perspective kept).
    """
    logger.info(f"[EXTRACT] Extracting game logs for {season} ...")
    frames = []
    for abbr, full_name in TEAM_ABBR_MAP.items():
        try:
            sched = schedule_and_record(season, abbr)
            if sched is not None and not sched.empty:
                sched = sched.copy()
                sched["_team_abbr"] = abbr
                sched["_team_name"] = full_name
                sched["season"] = season
                frames.append(sched)
        except Exception:
            logger.debug(f"   skipped {abbr}")
            continue
        time.sleep(0.3)  # be kind to Baseball Reference

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"   -> {len(combined)} raw schedule rows extracted.")
    return combined


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANSFORM  — clean, normalise, map columns
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_float(series: pd.Series) -> pd.Series:
    """Coerce a column to float, replacing non‑numeric with NaN."""
    return pd.to_numeric(series, errors="coerce")


def _strip_pct(series: pd.Series) -> pd.Series:
    """Remove trailing '%' and convert to decimal float (e.g. 25% → 0.25)."""
    if series.dtype == object:
        series = series.astype(str).str.rstrip("% ").str.strip()
    numeric = pd.to_numeric(series, errors="coerce")
    # If values are >1, assume they're percentages needing /100
    if numeric.dropna().empty:
        return numeric
    if numeric.dropna().median() > 1:
        return numeric / 100.0
    return numeric


def _fill_sabermetric_nulls(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """
    Handle NaN in advanced metrics:
      • WAR / FIP / xFIP / SIERA  → fill with 0.0  (replacement‑level)
      • Rate stats (BABIP, K%, BB%, etc.) → fill with league median
    """
    replacement_level_cols = {"war", "fip", "xfip", "siera", "off", "defense", "bsr"}
    for col in cols:
        if col not in df.columns:
            continue
        if col in replacement_level_cols:
            df[col] = df[col].fillna(0.0)
        else:
            median_val = df[col].median()
            if pd.notna(median_val):
                df[col] = df[col].fillna(median_val)
            else:
                df[col] = df[col].fillna(0.0)
    return df


def transform_standings(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean standings DataFrame and align to MLBTeam schema."""
    if raw.empty:
        return raw

    df = raw.copy()

    # Normalise team name column (pybaseball uses 'Tm')
    team_col = "Tm" if "Tm" in df.columns else df.columns[0]
    df = df.rename(columns={team_col: "team_name"})

    # Parse numeric columns
    for col in ["W", "L", "W-L%", "GB"]:
        if col in df.columns:
            df[col] = _safe_float(df[col])

    rename_map = {
        "W": "wins",
        "L": "losses",
        "W-L%": "win_pct",
        "GB": "games_back",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Calculate run differential if run data exists
    if "R" in df.columns and "RA" in df.columns:
        df["runs_scored"] = _safe_float(df["R"]).astype("Int64")
        df["runs_allowed"] = _safe_float(df["RA"]).astype("Int64")
        df["run_differential"] = df["runs_scored"] - df["runs_allowed"]

    # Pythagorean expected win %:  RS^2 / (RS^2 + RA^2)
    if "runs_scored" in df.columns and "runs_allowed" in df.columns:
        rs = df["runs_scored"].astype(float)
        ra = df["runs_allowed"].astype(float)
        df["pythagorean_win_pct"] = np.where(
            (rs + ra) > 0,
            (rs ** 2) / (rs ** 2 + ra ** 2),
            np.nan,
        )

    # Keep only schema columns
    keep = [
        "team_name", "league", "division", "season",
        "wins", "losses", "win_pct", "games_back",
        "runs_scored", "runs_allowed", "run_differential",
        "pythagorean_win_pct",
    ]
    df = df[[c for c in keep if c in df.columns]]

    logger.info(f"[TRANSFORM] Transformed {len(df)} standing rows.")
    return df


def transform_batting(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean batting DataFrame and align to MLBPlayerBatting schema."""
    if raw.empty:
        return raw

    df = raw.copy()

    # Rename columns using map (only those present)
    rename = {k: v for k, v in BATTING_COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Convert percentage columns
    pct_cols = ["gb_pct", "fb_pct", "ld_pct", "hr_fb", "hard_hit_pct", "barrel_pct"]
    for col in pct_cols:
        if col in df.columns:
            df[col] = _strip_pct(df[col])

    # Ensure float types for sabermetric columns
    float_cols = [
        "avg", "obp", "slg", "ops", "iso", "war", "wrc_plus", "woba",
        "babip", "off", "defense", "bsr",
    ] + pct_cols
    for col in float_cols:
        if col in df.columns:
            df[col] = _safe_float(df[col])

    # Fill advanced metric NaNs
    df = _fill_sabermetric_nulls(df, float_cols)

    # Ensure player_id is string
    if "player_id" in df.columns:
        df["player_id"] = df["player_id"].astype(str)

    # Keep only mapped columns
    valid_cols = list(BATTING_COL_MAP.values())
    df = df[[c for c in valid_cols if c in df.columns]]

    logger.info(f"[TRANSFORM] Transformed {len(df)} batting rows.")
    return df


def transform_pitching(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean pitching DataFrame and align to MLBPlayerPitching schema."""
    if raw.empty:
        return raw

    df = raw.copy()

    rename = {k: v for k, v in PITCHING_COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Convert percentage columns
    pct_cols = [
        "k_pct", "bb_pct", "lob_pct", "gb_pct", "fb_pct",
        "hr_fb", "hard_hit_pct", "barrel_pct",
    ]
    for col in pct_cols:
        if col in df.columns:
            df[col] = _strip_pct(df[col])

    float_cols = [
        "era", "ip", "whip", "k_per_9", "bb_per_9", "hr_per_9",
        "k_bb_ratio", "war", "fip", "xfip", "siera", "babip",
    ] + pct_cols
    for col in float_cols:
        if col in df.columns:
            df[col] = _safe_float(df[col])

    df = _fill_sabermetric_nulls(df, float_cols)

    if "player_id" in df.columns:
        df["player_id"] = df["player_id"].astype(str)

    valid_cols = list(PITCHING_COL_MAP.values())
    df = df[[c for c in valid_cols if c in df.columns]]

    logger.info(f"[TRANSFORM] Transformed {len(df)} pitching rows.")
    return df


def transform_game_logs(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Transform schedule_and_record data into game‑log rows.
    Keep only home‑perspective rows to avoid duplicates.
    """
    if raw.empty:
        return raw

    df = raw.copy()

    # Filter to home games only (column usually contains '' for home or '@' for away)
    home_away_col = None
    for candidate in ["Home_Away", "Unnamed: 4", "H_A"]:
        if candidate in df.columns:
            home_away_col = candidate
            break

    if home_away_col:
        df = df[df[home_away_col].astype(str).str.strip().isin(["", "Home", "nan"])]

    # Build normalised game log
    result = pd.DataFrame()
    result["season"] = df["season"]

    # Parse date
    if "Date" in df.columns:
        result["game_date"] = pd.to_datetime(
            df["Date"].astype(str).str.replace(r"\s*\(\d+\)", "", regex=True)
            + f" {df['season'].iloc[0] if len(df) > 0 else datetime.now().year}",
            format="mixed",
            errors="coerce",
        ).dt.date
    else:
        result["game_date"] = None

    result["home_team"] = df.get("_team_name", "")
    result["away_team"] = df.get("Opp", "")

    # Scores
    if "R" in df.columns:
        result["home_score"] = _safe_float(df["R"]).astype("Int64")
    if "RA" in df.columns:
        result["away_score"] = _safe_float(df["RA"]).astype("Int64")
    if "home_score" in result.columns and "away_score" in result.columns:
        result["total_runs"] = result["home_score"] + result["away_score"]
        result["run_line"] = result["home_score"] - result["away_score"]
        result["winning_team"] = np.where(
            result["home_score"] > result["away_score"],
            result["home_team"],
            result["away_team"],
        )
        result["losing_team"] = np.where(
            result["home_score"] > result["away_score"],
            result["away_team"],
            result["home_team"],
        )

    # Innings (if available)
    if "Inn" in df.columns:
        result["innings"] = _safe_float(df["Inn"]).astype("Int64")
        result["is_extra_innings"] = np.where(
            result["innings"].fillna(9) > 9, 1, 0
        )
    else:
        result["innings"] = 9
        result["is_extra_innings"] = 0

    # Drop rows without a valid date
    result = result.dropna(subset=["game_date"])

    # De-duplicate by (game_date, home_team, away_team)
    result = result.drop_duplicates(subset=["game_date", "home_team", "away_team"])

    logger.info(f"[TRANSFORM] Transformed {len(result)} game log rows.")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  LOAD  — upsert DataFrames into PostgreSQL
# ═══════════════════════════════════════════════════════════════════════════════

def _upsert_dataframe(
    engine,
    df: pd.DataFrame,
    model,
    conflict_columns: list[str],
    chunk_size: int = BULK_INSERT_CHUNK,
) -> int:
    """
    Perform a PostgreSQL ON CONFLICT … DO UPDATE (upsert) in chunks.

    Parameters
    ----------
    engine : SQLAlchemy Engine
    df : cleaned DataFrame whose columns match the model's column names
    model : SQLAlchemy ORM class
    conflict_columns : columns forming the unique constraint
    chunk_size : rows per INSERT statement

    Returns
    -------
    int : total rows upserted
    """
    if df.empty:
        return 0

    table = model.__table__
    records = df.to_dict(orient="records")

    # Columns to update on conflict (everything except PK and conflict keys)
    update_cols = [
        c.name for c in table.columns
        if c.name not in conflict_columns
        and c.name != "id"
        and c.name != "created_at"
    ]

    total = 0
    with engine.begin() as conn:
        for i in range(0, len(records), chunk_size):
            chunk = records[i : i + chunk_size]
            stmt = pg_insert(table).values(chunk)
            update_dict = {col: stmt.excluded[col] for col in update_cols if col in stmt.excluded}
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns,
                set_=update_dict,
            )
            conn.execute(stmt)
            total += len(chunk)

    return total


def load_standings(engine, df: pd.DataFrame) -> int:
    """Upsert team standings."""
    if df.empty:
        return 0
    count = _upsert_dataframe(
        engine, df, MLBTeam,
        conflict_columns=["team_name", "season"],
    )
    logger.info(f"[LOAD] Loaded {count} team standings rows.")
    return count


def load_batting(engine, df: pd.DataFrame) -> int:
    """Upsert batting stats."""
    if df.empty:
        return 0
    count = _upsert_dataframe(
        engine, df, MLBPlayerBatting,
        conflict_columns=["player_name", "team", "season"],
    )
    logger.info(f"[LOAD] Loaded {count} batting rows.")
    return count


def load_pitching(engine, df: pd.DataFrame) -> int:
    """Upsert pitching stats."""
    if df.empty:
        return 0
    count = _upsert_dataframe(
        engine, df, MLBPlayerPitching,
        conflict_columns=["player_name", "team", "season"],
    )
    logger.info(f"[LOAD] Loaded {count} pitching rows.")
    return count


def load_game_logs(engine, df: pd.DataFrame) -> int:
    """Upsert game logs."""
    if df.empty:
        return 0
    count = _upsert_dataframe(
        engine, df, MLBGameLog,
        conflict_columns=["game_date", "home_team", "away_team"],
    )
    logger.info(f"[LOAD] Loaded {count} game log rows.")
    return count


# ═══════════════════════════════════════════════════════════════════════════════
#  ORCHESTRATOR  — full ETL pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(
    season: Optional[int] = None,
    skip_standings: bool = False,
    skip_batting: bool = False,
    skip_pitching: bool = False,
    skip_game_logs: bool = False,
):
    """Execute the complete Extract → Transform → Load pipeline."""
    season = season or DEFAULT_SEASON or datetime.now().year
    logger.info("=" * 72)
    logger.info(f">>> MLB Data Pipeline -- Season {season}")
    logger.info(f"   Database: {DATABASE_URL.split('@')[-1]}")
    logger.info("=" * 72)

    t0 = time.time()

    # ── Initialise DB ────────────────────────────────────────────────────
    engine = get_engine(DATABASE_URL)
    init_db(engine)

    summary = {}

    # ── Standings ────────────────────────────────────────────────────────
    if not skip_standings:
        raw = extract_standings(season)
        clean = transform_standings(raw)
        summary["standings"] = load_standings(engine, clean)

    # ── Batting ──────────────────────────────────────────────────────────
    if not skip_batting:
        raw = extract_batting(season)
        clean = transform_batting(raw)
        summary["batting"] = load_batting(engine, clean)

    # ── Pitching ─────────────────────────────────────────────────────────
    if not skip_pitching:
        raw = extract_pitching(season)
        clean = transform_pitching(raw)
        summary["pitching"] = load_pitching(engine, clean)

    # ── Game Logs ────────────────────────────────────────────────────────
    if not skip_game_logs:
        raw = extract_game_logs(season)
        clean = transform_game_logs(raw)
        summary["game_logs"] = load_game_logs(engine, clean)

    elapsed = time.time() - t0

    # ── Summary ──────────────────────────────────────────────────────────
    logger.info("=" * 72)
    logger.info(f"[DONE] Pipeline completed in {elapsed:.1f}s")
    for stage, count in summary.items():
        logger.info(f"   * {stage:<15s} -> {count:>6,} rows")
    logger.info("=" * 72)

    return summary


# ══════════════════════════════════════════════════════════════════════════════
#  CLI entry‑point
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="MLB Sabermetrics Data Ingestion Pipeline",
    )
    parser.add_argument(
        "--season", type=int, default=None,
        help="Season year to ingest (default: current year)",
    )
    parser.add_argument(
        "--skip-standings", action="store_true",
        help="Skip standings ingestion",
    )
    parser.add_argument(
        "--skip-batting", action="store_true",
        help="Skip batting stats ingestion",
    )
    parser.add_argument(
        "--skip-pitching", action="store_true",
        help="Skip pitching stats ingestion",
    )
    parser.add_argument(
        "--skip-game-logs", action="store_true",
        help="Skip game logs ingestion",
    )

    args = parser.parse_args()

    try:
        run_pipeline(
            season=args.season,
            skip_standings=args.skip_standings,
            skip_batting=args.skip_batting,
            skip_pitching=args.skip_pitching,
            skip_game_logs=args.skip_game_logs,
        )
    except KeyboardInterrupt:
        logger.warning("[STOP] Pipeline interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"[FATAL] Pipeline failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
