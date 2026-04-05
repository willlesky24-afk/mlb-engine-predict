import React from 'react';
import { Play, TrendingUp, AlertTriangle } from 'lucide-react';
import usePredictEngine from '../../hooks/usePredictEngine';

export default function PredictionDashboard() {
  const { loading, error, predictionData, runPrediction } = usePredictEngine();

  return (
    <div className="bg-surface rounded-xl border border-white/5 p-6 shadow-2xl h-full flex flex-col relative overflow-hidden">
      
      <div className="flex items-center justify-between mb-6 z-10 border-b border-white/5 pb-4">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <span className="bg-accent/20 text-accent p-1 rounded"><TrendingUp size={20} /></span> 
          Resultados del Motor Predictivo
        </h2>
      </div>

      <div className="flex-grow flex flex-col mb-6 z-10 overflow-y-auto">
        {!predictionData && !loading && !error && (
          <div className="text-center my-auto p-8 border-2 border-dashed border-white/10 rounded-xl bg-background/30">
            <div className="bg-surfaceHover w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 shadow-inner">
              <TrendingUp size={24} className="text-textMuted" />
            </div>
            <p className="text-textMuted font-medium">Panel en Reposo</p>
            <p className="text-xs text-textMuted/70 mt-2">Personaliza el Lineup y calcula la métrica Sabermétrica.</p>
          </div>
        )}

        {loading && (
          <div className="text-center animate-pulse my-auto p-8 bg-background/30 rounded-xl">
            <div className="w-12 h-12 border-4 border-primary/30 border-t-primary rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-primary font-semibold">Ejecutando FastAPI & Monte Carlo...</p>
            <p className="text-xs text-textMuted mt-1">Computando miles de iteraciones matemáticas</p>
          </div>
        )}

        {error && (
          <div className="text-center text-red-400 my-auto p-8 bg-red-900/10 rounded-xl border border-red-500/20">
            <AlertTriangle size={32} className="mx-auto mb-2" />
            <p className="font-bold">Error de Conexión</p>
            <p className="text-xs mt-1">{error}</p>
          </div>
        )}

        {predictionData && !loading && (
          <div className="w-full animate-in fade-in zoom-in duration-300 flex flex-col gap-6">
            
            {/* 1. Probabilidad de Victoria (Gráfico de Barra de Progreso) */}
            <div className="bg-background/50 p-4 rounded-xl border border-white/5 shadow-sm">
              <h3 className="text-sm font-semibold text-textMuted mb-4">Probabilidad de Victoria Global</h3>
              <div className="flex justify-between text-xs font-bold mb-2">
                <span className="text-primary">{predictionData.teamA} ({predictionData.winProbabilityA.toFixed(1)}%)</span>
                <span className="text-accent">{predictionData.teamB} ({predictionData.winProbabilityB.toFixed(1)}%)</span>
              </div>
              <div className="w-full h-4 bg-surfaceHover rounded-full overflow-hidden flex shadow-inner">
                <div 
                  style={{ width: `${predictionData.winProbabilityA}%` }} 
                  className="h-full bg-gradient-to-r from-blue-600 to-primary transition-all duration-1000"
                ></div>
                <div 
                  style={{ width: `${predictionData.winProbabilityB}%` }} 
                  className="h-full bg-gradient-to-l from-emerald-600 to-accent transition-all duration-1000"
                ></div>
              </div>
            </div>

            {/* 2. Marcador Estimado (Texto Grande) */}
            <div className="text-center flex items-center justify-center gap-8 py-2">
              <div className="flex-1 text-right">
                <p className="text-xs text-textMuted uppercase tracking-widest mb-1">{predictionData.teamA}</p>
                <span className="text-6xl font-black text-textMain drop-shadow-md">{predictionData.teamA_score}</span>
              </div>
              <div className="text-textMuted font-bold text-sm bg-surfaceHover px-3 py-1 rounded-full border border-white/5">
                FINAL EST.
              </div>
              <div className="flex-1 text-left">
                <p className="text-xs text-textMuted uppercase tracking-widest mb-1">{predictionData.teamB}</p>
                <span className="text-6xl font-black text-textMain drop-shadow-md">{predictionData.teamB_score}</span>
              </div>
            </div>

            {/* 3. Probabilidades de Margen (Tabla Minimalista) */}
            <div className="bg-background/20 rounded-xl border border-white/5 overflow-hidden shadow-sm">
              <div className="bg-surfaceHover px-4 py-2 border-b border-white/5">
                <h3 className="text-xs font-semibold text-textMuted uppercase tracking-wider">Distribución de Margen Exacto</h3>
              </div>
              <table className="w-full text-sm text-left">
                <tbody>
                  <tr className="border-b border-white/5">
                    <td className="px-4 py-2 text-textMuted">{predictionData.teamA} por 1+ Carreras</td>
                    <td className="px-4 py-2 text-right font-mono font-medium text-textMain">~11.6%</td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="px-4 py-2 text-textMuted">{predictionData.teamB} por 1+ Carreras</td>
                    <td className="px-4 py-2 text-right font-mono font-medium text-textMain">~11.5%</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2 text-textMuted font-semibold text-primary">Margen de Volatilidad (Alert)</td>
                    <td className="px-4 py-2 text-right font-mono font-bold text-primary">
                      {predictionData.alert ? 'ALTO RIESGO' : 'ESTABLE'}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            
          </div>
        )}
      </div>

      <button 
        onClick={runPrediction}
        disabled={loading}
        className={`w-full py-4 rounded-lg font-bold text-lg flex items-center justify-center gap-2 transition-all z-10 shadow-xl shrink-0
          ${loading 
            ? 'bg-surfaceHover text-textMuted cursor-not-allowed' 
            : 'bg-primary hover:bg-blue-600 text-white shadow-primary/20 hover:shadow-primary/40'
          }`}
      >
        <Play size={20} className={loading ? 'hidden' : 'block'} />
        {loading ? 'Simulando Lineup...' : 'Lanzar Simulación MLB'}
      </button>

    </div>
  );
}
