import React from 'react';
import MatchupSelector from './components/ControlPanel/MatchupSelector';
import LineupBuilder from './components/ControlPanel/LineupBuilder';
import PredictionDashboard from './components/ResultsPanel/PredictionDashboard';
import useMatchupStore from './store/useMatchupStore';

function App() {
  const { teamA, teamB } = useMatchupStore();

  return (
    <div className="min-h-screen bg-background flex flex-col items-center py-10 px-4">
      {/* Header */}
      <header className="w-full max-w-7xl mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent tracking-tight">
            MLB Sabermetrics Predictor
          </h1>
          <p className="text-textMuted mt-1">Stochastic Inning-by-Inning Monte Carlo Engine</p>
        </div>
      </header>

      {/* Main Layout - 2 Columns */}
      <main className="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column - Control Panel (col-span 7) */}
        <section className="lg:col-span-7 flex flex-col gap-6">
          <div className="bg-surface rounded-xl border border-white/5 p-6 shadow-2xl">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <span className="bg-primary/20 text-primary p-1 rounded">⚙️</span> 
              Control Panel
            </h2>
            
            <MatchupSelector />
            
            <div className="mt-8">
              <LineupBuilder />
            </div>
          </div>
        </section>

        {/* Right Column - Results Panel (col-span 5) */}
        <section className="lg:col-span-5 flex flex-col">
          <PredictionDashboard />
        </section>

      </main>
    </div>
  );
}

export default App;
