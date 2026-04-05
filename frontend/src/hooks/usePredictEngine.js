import { useState } from 'react';
import useMatchupStore from '../store/useMatchupStore';

export default function usePredictEngine() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [predictionData, setPredictionData] = useState(null);
  
  const matchupState = useMatchupStore();

  const runPrediction = async () => {
    setLoading(true);
    setError(null);
    setPredictionData(null);
    
    // Preparar el JSON que viaja al backend basándonos en el store
    const payload = {
      teamA: matchupState.teamA,
      teamB: matchupState.teamB,
      inactivePlayersA: matchupState.inactivePlayersA,
      inactivePlayersB: matchupState.inactivePlayersB,
      starterA: matchupState.starterA,
      starterB: matchupState.starterB,
      // Pasamos raw fatigue o boolean. Aca mandamos raw metrics si el backend las requiere,
      // o un flag para compatibilidad con la API que construimos en el turno previo.
      fatigueA: matchupState.fatigueA > 60,
      fatigueB: matchupState.fatigueB > 60
    };

    try {
      // Endpoint a nuestro Flask (puerto 5050 dictado en el paso anterior)
      const response = await fetch('http://127.0.0.1:5050/api/predict', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`API Connection Failed: ${response.status} - ${response.statusText}`);
      }

      const data = await response.json();
      setPredictionData(data);
    } catch (err) {
      console.error(err);
      setError(err.message || 'Error desconocido contactando al backend Predictivo MLB.');
    } finally {
      setLoading(false);
    }
  };

  return { loading, error, predictionData, runPrediction };
}
