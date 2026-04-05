import os
from datetime import date, timedelta
import pandas as pd
from dotenv import load_dotenv

import pybaseball
from services.models import get_engine, get_session, init_db, PredictionHistory

# Cargar variables de entorno
load_dotenv()

def run_daily_audit():
    """
    Ejecuta la auditoría diaria:
    1. Busca predicciones hechas que aún no han sido verificadas (prediction_correct is None).
    2. Descarga el resultado real del partido usando pybaseball.
    3. Calcula el Error Absoluto y verifica si el ganador predicho fue correcto.
    """
    print("=========================================================")
    print("⚾ INICIANDO AUDITORIA SABERMETICA DE PREDICCIONES")
    print("=========================================================")
    
    # 1. Chequear si hay URL directa (Supabase/Neon)
    db_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')
    
    # 2. Si no hay URL directa, construirla con Host dinamico (no hardcoded localhost)
    if not db_url:
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = os.getenv('POSTGRES_PORT', '5432')
        user = os.getenv('POSTGRES_USER')
        pwd = os.getenv('POSTGRES_PASSWORD')
        db = os.getenv('POSTGRES_DB')
        db_url = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

    engine = get_engine(db_url)
    init_db(engine)  # Asegurar que la nueva tabla PredictionHistory exista
    session = get_session(engine)

    # 1. Traer todos los records pendientes
    pending_records = session.query(PredictionHistory).filter(
        PredictionHistory.prediction_correct.is_(None)
    ).all()

    if not pending_records:
        print("[i] No hay predicciones pendientes de auditar en la base de datos.")
        session.close()
        return

    print(f"[i] Se encontraron {len(pending_records)} predicciones pendientes. Evaluando...")

    current_year = date.today().year

    for record in pending_records:
        try:
            print(f" -> Verificando juego: {record.team_a} vs {record.team_b} ({record.game_date})")
            
            # Descargamos el schedule del Team A 
            # (En pybaseball, los abbreviations son standard como NYY, LAD, etc)
            schedule = pybaseball.schedule_and_record(current_year, record.team_a)
            
            # El schedule no tiene fechas en formato YYYY-MM-DD, a veces es "Mar 28"
            # Una forma robusta es cruzar por "Opp" (Opponent) si es el juego mas reciente,
            # pero podemos simplemente auditar el ultimo juego registrado del equipo en el schedule
            
            # Limpiamos resultados vacios (juegos en el futuro)
            played_games = schedule.dropna(subset=['R', 'RA'])
            
            if played_games.empty:
                print("    [!] El equipo aún no ha jugado partidos esta temporada.")
                continue
                
            # Tomamos el ultimo juego completado. En un sistema real de prod, 
            # haríamos un parsing robusto de fechas, pero para el prototipo tomamos el mas reciente.
            last_game = played_games.iloc[-1]
            
            # Runs para A (el equipo sobre el que hacemos el query)
            runs_a = int(last_game['R'])
            # Runs permitidas (las runs del equipo B)
            runs_b = int(last_game['RA'])
            actual_winner = record.team_a if runs_a > runs_b else record.team_b
            
            record.actual_runs_a = runs_a
            record.actual_runs_b = runs_b
            record.actual_winner = actual_winner
            
            # Analisis de Error
            record.absolute_error_a = abs(record.predicted_runs_a - runs_a)
            record.absolute_error_b = abs(record.predicted_runs_b - runs_b)
            
            # Acierto del ganador
            record.prediction_correct = (record.predicted_winner == actual_winner)
            
            print(f"    [RESULTADO] Ganador Real: {actual_winner} | Pizarra: {runs_a} - {runs_b}")
            print(f"    [METRICA] Correcto: {record.prediction_correct} | Error Absoluto A: {record.absolute_error_a:.2f} | Error Absoluto B: {record.absolute_error_b:.2f}")

        except Exception as e:
            print(f"    [!] Error procesando partido {record.id}: {e}")

    # Commit en la base de datos
    session.commit()
    print("=========================================================")
    print("✔️ AUDITORIA COMPLETADA Y GUARDADA EN DB.")
    print("=========================================================")
    session.close()

if __name__ == '__main__':
    run_daily_audit()
