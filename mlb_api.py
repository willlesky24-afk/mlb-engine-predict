import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import date
import sys

# Import our predictive models
from models.monte_carlo_sim import MLBMonteCarlo, TeamSimProfile
from models.mlb_engine import predict_matchup, TeamInput

# Database Integration
from services.models import get_engine, get_session, init_db, PredictionHistory

# Force UTF-8 for Windows console encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = Flask(__name__)
CORS(app) # Allow React frontend to access

def get_ml_weights():
    # Intenta leer la salida optima del auto_tuner
    path = os.path.join(os.path.dirname(__file__), 'models', 'weights_config.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {
        "ops_weight": 1.0, 
        "starter_fip_weight": 1.0, 
        "bullpen_fip_weight": 1.0, 
        "fatigue_penalty": 0.15
    }

@app.route('/api/predict', methods=['POST'])
def predict_game():
    data = request.json
    team_a_abbr = data.get('teamA', 'NYY')
    team_b_abbr = data.get('teamB', 'LAD')
    
    # Extraer pesos del optimizador
    w = get_ml_weights()
    
    # Team A Profile (Away) con pesos adaptativos
    team_a_runs = 5.12 * w.get('ops_weight', 1.0)
    team_a_allowed = 3.98 * w.get('starter_fip_weight', 1.0)
    
    # Team B Profile (Home) con pesos adaptativos
    team_b_runs = 4.87 * w.get('ops_weight', 1.0)
    team_b_allowed = 3.65 * w.get('starter_fip_weight', 1.0)

    # Variance and Fatigue (Could be sent from frontend UI)
    fatigue_a = data.get('fatigueA', False)
    fatigue_b = data.get('fatigueB', False)
    
    # Add simple mapping for names
    names = {
        'NYY': 'New York Yankees',
        'LAD': 'Los Angeles Dodgers',
        'HOU': 'Houston Astros',
        'ATL': 'Atlanta Braves',
        'BAL': 'Baltimore Orioles',
        'PHI': 'Philadelphia Phillies',
    }

    yankees = TeamSimProfile(
        name=names.get(team_a_abbr, team_a_abbr),
        avg_runs_scored=team_a_runs,
        avg_runs_allowed=team_a_allowed,
        sabermetric_variance=1.45 if team_a_abbr == 'NYY' else 1.10,
        bullpen_fatigued=fatigue_a,
        is_home=False
    )

    dodgers = TeamSimProfile(
        name=names.get(team_b_abbr, team_b_abbr),
        avg_runs_scored=team_b_runs,
        avg_runs_allowed=team_b_allowed,
        sabermetric_variance=1.10,
        bullpen_fatigued=fatigue_b,
        is_home=True
    )

    # 1. Run Monte Carlo
    mc_engine = MLBMonteCarlo(iterations=1000) # 1000 for fast web response
    mc_result = mc_engine.run_simulation(yankees, dodgers)

    # =========================================================
    # GUARDAR PREDICCIÓN EN BASE DE DATOS (FEEDBACK LOOP)
    # =========================================================
    try:
        # Recuperar credenciales del modo dinamico (Supabase o Localhost)
        db_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')
        if not db_url:
            host = os.getenv('POSTGRES_HOST', 'localhost')
            port = os.getenv('POSTGRES_PORT', '5432')
            user = os.getenv('POSTGRES_USER')
            pwd = os.getenv('POSTGRES_PASSWORD')
            db = os.getenv('POSTGRES_DB')
            db_url = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
            
        engine = get_engine(db_url)
        session = get_session(engine)
        
        history_record = PredictionHistory(
            game_date=date.today(),
            team_a=yankees.name,
            team_b=dodgers.name,
            predicted_winner=yankees.name if mc_result.win_prob_a > 0.5 else dodgers.name,
            predicted_runs_a=mc_result.team_a_avg_runs,
            predicted_runs_b=mc_result.team_b_avg_runs,
            win_probability_a=mc_result.win_prob_a * 100,
            win_probability_b=mc_result.win_prob_b * 100,
            weights=w  # Pesos de Machine Learning al momento de predecir
        )
        session.add(history_record)
        session.commit()
        session.close()
        print(f"[i] Prediccion {yankees.name} vs {dodgers.name} guardada en DB para auditoria futura.")
    except Exception as e:
        print(f"[!] Error guardando historial en la Base de Datos: {e}")

    # 2. Setup response data
    response = {
        "teamA": yankees.name,
        "teamB": dodgers.name,
        "teamA_score": round(mc_result.team_a_avg_runs),
        "teamB_score": round(mc_result.team_b_avg_runs),
        "winProbabilityA": mc_result.win_prob_a * 100,
        "winProbabilityB": mc_result.win_prob_b * 100,
        "alert": mc_result.volatility_alert,
        "base_skellam_prob": mc_result.skellam_prob_a * 100,
        "projected_runs_a": round(mc_result.team_a_avg_runs, 2),
        "projected_runs_b": round(mc_result.team_b_avg_runs, 2),
        "over_under_85": (mc_result.team_a_avg_runs + mc_result.team_b_avg_runs) > 8.5
    }

    return jsonify(response)

if __name__ == '__main__':
    print("=========================================================")
    print("⚾ API DEL MOTOR PREDICTIVO MLB CORRIENDO PERFECTAMENTE")
    print("Acceso Local: http://127.0.0.1:5050")
    print("YA PUEDES PRESIONAR EL BOTON EN LA PAGINA WEB")
    print("=========================================================")
    app.run(debug=True, host='127.0.0.1', port=5050)
