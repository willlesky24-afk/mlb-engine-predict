"""
Diagnóstico rápido de conexión a Supabase.
Verifica qué tablas existen y cuántas filas tienen.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

db_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')
if not db_url:
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    user = os.getenv('POSTGRES_USER')
    pwd = os.getenv('POSTGRES_PASSWORD')
    db = os.getenv('POSTGRES_DB')
    db_url = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

print(f"Conectando a: {db_url.split('@')[-1]}")

engine = create_engine(db_url)

tables = [
    'mlb_team',
    'mlb_player_batting',
    'mlb_player_pitching',
    'mlb_game_log',
    'mlb_prediction_history'
]

with engine.connect() as conn:
    print("\n===== DIAGNOSTICO SUPABASE =====")
    for t in tables:
        try:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
            count = result.scalar()
            status = "✅ CON DATOS" if count > 0 else "❌ VACIA"
            print(f"  {t:30s} -> {count:>6} filas  {status}")
        except Exception as e:
            print(f"  {t:30s} -> ⚠️ NO EXISTE ({e})")
    print("================================")
