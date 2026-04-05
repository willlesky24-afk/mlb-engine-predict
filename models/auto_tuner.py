import os
import json
import numpy as np
from scipy.optimize import minimize
from sqlalchemy import desc

from services.models import get_engine, get_session, init_db, PredictionHistory
from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'weights_config.json')

# ====== PARÁMETROS BASE ======
# Si no existe configuración, empezamos con la base heurística
DEFAULT_WEIGHTS = {
    "ops_weight": 1.0,
    "starter_fip_weight": 0.65,
    "bullpen_fip_weight": 0.35,
    "fatigue_penalty": 0.15
}

def load_current_weights():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return DEFAULT_WEIGHTS.copy()

def save_weights(weights):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(weights, f, indent=4)
    print(f"[+] Nuevos pesos guardados en {CONFIG_PATH}")

def calculate_metrics(y_true_prob, y_pred_prob, y_true_runs, y_pred_runs):
    """
    Calcula Log Loss (para victorias) y RMSE (para carreras).
    """
    # Evitar log(0)
    eps = 1e-15
    y_pred_prob = np.clip(y_pred_prob, eps, 1 - eps)
    
    # Log Loss Binario
    log_loss = -np.mean(y_true_prob * np.log(y_pred_prob) + (1 - y_true_prob) * np.log(1 - y_pred_prob))
    
    # RMSE
    rmse = np.sqrt(np.mean((y_true_runs - y_pred_runs)**2))
    
    return log_loss, rmse

def optimize_weights():
    """
    Núcleo de Machine Learning: Feedback Loop.
    Busca minimizar la divergencia entre la predicción y la realidad recolectada por el auditor.
    """
    print("=========================================================")
    print("🧠 INICIANDO AUTO-TUNER DE MACHINE LEARNING")
    print("=========================================================")
    
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
    
    # Extraer los últimos 100 juegos YA auditados
    records = session.query(PredictionHistory).filter(
        PredictionHistory.prediction_correct.is_not(None)
    ).order_by(desc(PredictionHistory.game_date)).limit(100).all()

    if len(records) < 10:
        print(f"[i] Insuficientes datos para entrenar (Se requieren al menos 10). Tienes: {len(records)}.")
        session.close()
        return

    print(f"[i] Entrenando sobre un batch de {len(records)} juegos históricos...")

    # Extraer variables X, Y
    # Para el propósito del optimizador asumimos que los 'weights' antiguos
    # en la DB contienen los stats pelados de los equipos para reconstruir la funcion
    
    runs_true_a = np.array([r.actual_runs_a for r in records])
    runs_true_b = np.array([r.actual_runs_b for r in records])
    
    # Arrays combinados para RMSE
    Y_runs_true = np.concatenate([runs_true_a, runs_true_b])
    
    # Probabilidad Real Binaria (1 si ganó A, 0 si A perdió)
    # y_true_prob_a = 1.0 -> El equipo A ganó
    Y_win_true = np.array([1.0 if r.actual_winner == r.team_a else 0.0 for r in records])
    Y_win_pred_old = np.array([r.win_probability_a / 100.0 for r in records if r.win_probability_a])
    
    if len(Y_win_pred_old) != len(Y_win_true):
         # Si hay nulos por simulaciones viejas corruptas
         print("[!] Existes registros sin 'win_probability_a' guardado. Cancelando entrenamiento.")
         session.close()
         return

    # Baseline Error usando la configuracion con la que se predijo originalmente
    old_runs_pred = np.concatenate([
        np.array([r.predicted_runs_a for r in records]),
        np.array([r.predicted_runs_b for r in records])
    ])
    
    baseline_log_loss, baseline_rmse = calculate_metrics(Y_win_true, Y_win_pred_old, Y_runs_true, old_runs_pred)
    baseline_combined_error = baseline_log_loss + (baseline_rmse * 0.1) # Score ponderado combinado
    
    print(f"📊 [BASELINE] Log Loss Inicial: {baseline_log_loss:.4f} | RMSE Inicial: {baseline_rmse:.4f}")

    current_config = load_current_weights()
    initial_guess = [
        current_config['ops_weight'],
        current_config['starter_fip_weight'],
        current_config['bullpen_fip_weight'],
        current_config['fatigue_penalty']
    ]

    # Bounds estrictos para evitar Overfitting (Sobrea-ajuste)
    # No queremos que el modelo asigne pesos absurdos (ej: Fatigue = 0.999) 
    # solo por el ruido de 10 juegos anómalos.
    bounds = [
        (0.5, 1.5),     # ops_weight
        (0.4, 0.8),     # starter_fip_weight (Entre 40% y 80%)
        (0.2, 0.6),     # bullpen_fip_weight (Entre 20% y 60%)
        (0.05, 0.3)     # fatigue_penalty    (Max 30% castigo)
    ]

    def cost_function(params):
        ops_w, starter_w, bp_w, fatigue_p = params
        
        simulated_runs_pred = []
        simulated_win_probs = []
        
        # Re-simulamos usando los parametros matematicos guardados en record.weights
        for r in records:
            # Dado que este es un Engine Predictivo, en un caso de producción real inyectamos 
            # las variables crudas guardadas en "weights" (ej: raw_ops_a, raw_fip_a).
            # Para este scope, como ajuste algoritmico, escalamos las predicciones viejas
            # proporcionales a la mutación de los hiperparámetros respecto del default.
            
            # Simulated scale factor
            scale_a = (ops_w / current_config['ops_weight']) - (fatigue_p * 0.5) 
            scale_b = (starter_w / current_config['starter_fip_weight'])
            
            # Generamos nuevas predicciones basadas en la mutacion
            new_r_a = r.predicted_runs_a * max(0.5, scale_a)
            new_r_b = r.predicted_runs_b * max(0.5, scale_b)
            
            # Probabilidad basica correlacionada (Logit proxy simple)
            diff = new_r_a - new_r_b
            new_prob_a = 1 / (1 + np.exp(-diff))
            
            simulated_runs_pred.append(new_r_a)
            simulated_runs_pred.append(new_r_b)
            simulated_win_probs.append(new_prob_a)
            
        c_log_loss, c_rmse = calculate_metrics(Y_win_true, np.array(simulated_win_probs), Y_runs_true, np.array(simulated_runs_pred))
        
        # L2 Regularization Penalty para evitar que se desvíe demasiado del conocimiento base (Ridge)
        l2_penalty = 0.05 * np.sum((np.array(params) - np.array(initial_guess))**2)
        
        return c_log_loss + (c_rmse * 0.1) + l2_penalty

    # Ejecutar la Optimizacion L-BFGS-B de Scipy
    print("\n[+] Optimizador L-BFGS-B corriendo convergenciación...")
    result = minimize(cost_function, initial_guess, method='L-BFGS-B', bounds=bounds)

    if result.success:
        new_combined_error = result.fun
        improvement = (baseline_combined_error - new_combined_error) / baseline_combined_error
        
        print(f"\n✅ Convergencia Alcanzada. Score Optimizado: {new_combined_error:.4f}")
        print(f"📈 Mejora de precisión: {improvement*100:.2f}%")
        
        # Umbral del 2% solicitado
        if improvement >= 0.02:
            print("\n[!] CRITERIO DE MEJORA > 2% SUPERADO. Actualizando pesos del servidor...")
            optimized_weights = {
                "ops_weight": round(result.x[0], 3),
                "starter_fip_weight": round(result.x[1], 3),
                "bullpen_fip_weight": round(result.x[2], 3),
                "fatigue_penalty": round(result.x[3], 3)
            }
            save_weights(optimized_weights)
            print("Nuevos Pesos Aprobados:", json.dumps(optimized_weights, indent=2))
        else:
            print("\n[-] La mejora es menor al 2% (ruido estadístico). Mantenemos los pesos actuales para evitar Overfitting.")
    else:
        print("\n[x] El optimizador falló en converger. Mantenemos hiperparámetros actuales.")

    session.close()

if __name__ == '__main__':
    optimize_weights()
