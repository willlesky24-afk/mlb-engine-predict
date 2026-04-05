"""
=============================================================================
 MLB Sabermetrics — SQLAlchemy ORM Schema  (PostgreSQL)
 Designed for predictive modelling & advanced analytics.
=============================================================================
Tables:
  • mlb_team             – franchise‑level season aggregates
  • mlb_player_batting   – per‑player batting lines  (traditional + sabermetric)
  • mlb_player_pitching  – per‑player pitching lines (traditional + sabermetric)
  • mlb_game_log         – game‑level results for modelling spreads / totals
=============================================================================
"""

from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Boolean,
    JSON,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


# ──────────────────────────────────────────────────────────────────────────────
#  MLB_Team  – season‑level team standings & aggregates
# ──────────────────────────────────────────────────────────────────────────────
class MLBTeam(Base):
    __tablename__ = "mlb_team"
    __table_args__ = (
        UniqueConstraint("team_name", "season", name="uq_team_season"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_name = Column(String(100), nullable=False, index=True)
    team_abbr = Column(String(10), nullable=True)
    league = Column(String(5), nullable=True)       # AL / NL
    division = Column(String(20), nullable=True)     # East / Central / West
    season = Column(Integer, nullable=False, index=True)

    # Record
    wins = Column(Integer, nullable=True)
    losses = Column(Integer, nullable=True)
    win_pct = Column(Float, nullable=True)
    games_back = Column(Float, nullable=True)

    # Run environment
    runs_scored = Column(Integer, nullable=True)
    runs_allowed = Column(Integer, nullable=True)
    run_differential = Column(Integer, nullable=True)

    # Pythagorean / BaseRuns expected W%
    pythagorean_win_pct = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MLBTeam {self.team_name} ({self.season})>"


# ──────────────────────────────────────────────────────────────────────────────
#  MLB_Player_Batting  – per‑player season batting stats
# ──────────────────────────────────────────────────────────────────────────────
class MLBPlayerBatting(Base):
    __tablename__ = "mlb_player_batting"
    __table_args__ = (
        UniqueConstraint("player_name", "team", "season", name="uq_batting_player_season"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_name = Column(String(150), nullable=False, index=True)
    player_id = Column(String(50), nullable=True)
    team = Column(String(100), nullable=True)
    season = Column(Integer, nullable=False, index=True)
    age = Column(Integer, nullable=True)

    # Traditional
    games = Column(Integer, nullable=True)
    pa = Column(Integer, nullable=True)     # plate appearances
    ab = Column(Integer, nullable=True)     # at‑bats
    hits = Column(Integer, nullable=True)
    doubles = Column(Integer, nullable=True)
    triples = Column(Integer, nullable=True)
    hr = Column(Integer, nullable=True)
    rbi = Column(Integer, nullable=True)
    runs = Column(Integer, nullable=True)
    sb = Column(Integer, nullable=True)     # stolen bases
    cs = Column(Integer, nullable=True)     # caught stealing
    bb = Column(Integer, nullable=True)     # walks
    so = Column(Integer, nullable=True)     # strikeouts
    hbp = Column(Integer, nullable=True)

    # Rate stats
    avg = Column(Float, nullable=True)      # batting average
    obp = Column(Float, nullable=True)      # on‑base %
    slg = Column(Float, nullable=True)      # slugging %
    ops = Column(Float, nullable=True)      # OBP + SLG
    iso = Column(Float, nullable=True)      # isolated power

    # Sabermetric
    war = Column(Float, nullable=True)      # Wins Above Replacement (fWAR)
    wrc_plus = Column(Float, nullable=True) # wRC+
    woba = Column(Float, nullable=True)     # weighted on‑base average
    babip = Column(Float, nullable=True)    # batting avg on balls in play
    off = Column(Float, nullable=True)      # offensive runs above avg
    defense = Column(Float, nullable=True)  # defensive runs above avg
    bsr = Column(Float, nullable=True)      # base‑running runs

    # Batted ball
    gb_pct = Column(Float, nullable=True)   # ground ball %
    fb_pct = Column(Float, nullable=True)   # fly ball %
    ld_pct = Column(Float, nullable=True)   # line drive %
    hr_fb = Column(Float, nullable=True)    # HR/FB ratio
    hard_hit_pct = Column(Float, nullable=True)
    barrel_pct = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MLBPlayerBatting {self.player_name} ({self.season})>"


# ──────────────────────────────────────────────────────────────────────────────
#  MLB_Player_Pitching  – per‑player season pitching stats
# ──────────────────────────────────────────────────────────────────────────────
class MLBPlayerPitching(Base):
    __tablename__ = "mlb_player_pitching"
    __table_args__ = (
        UniqueConstraint("player_name", "team", "season", name="uq_pitching_player_season"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_name = Column(String(150), nullable=False, index=True)
    player_id = Column(String(50), nullable=True)
    team = Column(String(100), nullable=True)
    season = Column(Integer, nullable=False, index=True)
    age = Column(Integer, nullable=True)

    # Traditional
    wins = Column(Integer, nullable=True)
    losses = Column(Integer, nullable=True)
    era = Column(Float, nullable=True)
    games = Column(Integer, nullable=True)
    games_started = Column(Integer, nullable=True)
    saves = Column(Integer, nullable=True)
    ip = Column(Float, nullable=True)       # innings pitched
    hits_allowed = Column(Integer, nullable=True)
    runs_allowed = Column(Integer, nullable=True)
    er = Column(Integer, nullable=True)     # earned runs
    hr_allowed = Column(Integer, nullable=True)
    bb = Column(Integer, nullable=True)
    so = Column(Integer, nullable=True)
    hbp = Column(Integer, nullable=True)

    # Rate stats
    whip = Column(Float, nullable=True)
    k_per_9 = Column(Float, nullable=True)
    bb_per_9 = Column(Float, nullable=True)
    hr_per_9 = Column(Float, nullable=True)
    k_bb_ratio = Column(Float, nullable=True)
    k_pct = Column(Float, nullable=True)
    bb_pct = Column(Float, nullable=True)

    # Sabermetric
    war = Column(Float, nullable=True)       # fWAR
    fip = Column(Float, nullable=True)       # Fielding Independent Pitching
    xfip = Column(Float, nullable=True)      # Expected FIP
    siera = Column(Float, nullable=True)     # Skill‑Interactive ERA
    lob_pct = Column(Float, nullable=True)   # Left On Base %
    gb_pct = Column(Float, nullable=True)    # ground ball %
    fb_pct = Column(Float, nullable=True)    # fly ball %
    hr_fb = Column(Float, nullable=True)     # HR/FB ratio
    babip = Column(Float, nullable=True)

    # Batted ball / Statcast
    hard_hit_pct = Column(Float, nullable=True)
    barrel_pct = Column(Float, nullable=True)
    avg_exit_velo = Column(Float, nullable=True)
    avg_spin_rate = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MLBPlayerPitching {self.player_name} ({self.season})>"


# ──────────────────────────────────────────────────────────────────────────────
#  MLB_Game_Log  – individual game results (for spread/total prediction)
# ──────────────────────────────────────────────────────────────────────────────
class MLBGameLog(Base):
    __tablename__ = "mlb_game_log"
    __table_args__ = (
        UniqueConstraint(
            "game_date", "home_team", "away_team", name="uq_game_log_entry"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_date = Column(Date, nullable=False, index=True)
    season = Column(Integer, nullable=False, index=True)

    home_team = Column(String(100), nullable=False, index=True)
    away_team = Column(String(100), nullable=False, index=True)

    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    total_runs = Column(Integer, nullable=True)
    run_line = Column(Float, nullable=True)      # home perspective

    winning_team = Column(String(100), nullable=True)
    losing_team = Column(String(100), nullable=True)

    home_hits = Column(Integer, nullable=True)
    away_hits = Column(Integer, nullable=True)
    home_errors = Column(Integer, nullable=True)
    away_errors = Column(Integer, nullable=True)

    innings = Column(Integer, nullable=True)      # 9 = regulation
    is_extra_innings = Column(Integer, nullable=True, default=0)

    venue = Column(String(200), nullable=True)
    attendance = Column(Integer, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<MLBGameLog {self.away_team}@{self.home_team} "
            f"{self.game_date}>"
        )


# ──────────────────────────────────────────────────────────────────────────────
#  PredictionHistory  – Audit trail for Monte Carlo & Skellam accuracy
# ──────────────────────────────────────────────────────────────────────────────
class PredictionHistory(Base):
    __tablename__ = "mlb_prediction_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_date = Column(Date, nullable=False, index=True)
    game_id = Column(String(100), nullable=True) # e.g. "NYY@LAD" or stats-api id
    
    team_a = Column(String(100), nullable=False)
    team_b = Column(String(100), nullable=False)
    
    # Engine Predictions
    predicted_winner = Column(String(100), nullable=False)
    predicted_runs_a = Column(Float, nullable=False)
    predicted_runs_b = Column(Float, nullable=False)
    win_probability_a = Column(Float, nullable=True)
    win_probability_b = Column(Float, nullable=True)
    
    # Context injected into model
    weights = Column(JSON, nullable=True)
    
    # Actual Results for Auditing
    actual_winner = Column(String(100), nullable=True)
    actual_runs_a = Column(Integer, nullable=True)
    actual_runs_b = Column(Integer, nullable=True)
    
    # Sabermetric Performance
    absolute_error_a = Column(Float, nullable=True)
    absolute_error_b = Column(Float, nullable=True)
    prediction_correct = Column(Boolean, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PredictionHistory {self.team_a} vs {self.team_b} on {self.game_date}>"


# ──────────────────────────────────────────────────────────────────────────────
#  Engine & Session factory
# ──────────────────────────────────────────────────────────────────────────────
def get_engine(database_url: str):
    """Create a SQLAlchemy engine from a PostgreSQL connection URL."""
    return create_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,
    )


def get_session(engine):
    """Return a scoped session bound to the given engine."""
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(engine):
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)
    print("[OK] Database schema initialised successfully.")
