import React, { useState } from 'react';
import useMatchupStore from '../../store/useMatchupStore';

// Mock Data
const MOCK_LINEUPS = {
  NYY: [
    { id: 1, name: 'Anthony Volpe', pos: 'SS' },
    { id: 2, name: 'Juan Soto', pos: 'RF' },
    { id: 3, name: 'Aaron Judge', pos: 'CF' },
    { id: 4, name: 'Cody Bellinger', pos: '1B' },
    { id: 5, name: 'Jazz Chisholm Jr.', pos: '3B' },
    { id: 6, name: 'Giancarlo Stanton', pos: 'DH' },
    { id: 7, name: 'Austin Wells', pos: 'C' },
    { id: 8, name: 'Alex Verdugo', pos: 'LF' },
    { id: 9, name: 'Oswaldo Cabrera', pos: '2B' },
  ],
  LAD: [
    { id: 1, name: 'Mookie Betts', pos: 'SS' },
    { id: 2, name: 'Shohei Ohtani', pos: 'DH' },
    { id: 3, name: 'Freddie Freeman', pos: '1B' },
    { id: 4, name: 'Teoscar Hernandez', pos: 'LF' },
    { id: 5, name: 'Will Smith', pos: 'C' },
    { id: 6, name: 'Max Muncy', pos: '3B' },
    { id: 7, name: 'Tommy Edman', pos: '2B' },
    { id: 8, name: 'Andy Pages', pos: 'RF' },
    { id: 9, name: 'James Outman', pos: 'CF' },
  ],
};

function BatterRow({ number, player, isActive, onToggle }) {
  return (
    <div className={`flex items-center justify-between p-2 rounded-md mb-1 transition-colors ${isActive ? 'bg-surfaceHover border border-white/5' : 'bg-background border border-white/5 opacity-50'}`}>
      <div className="flex items-center gap-3">
        <span className="text-textMuted font-mono text-xs w-4">{number}.</span>
        <div>
          <p className={`text-sm font-medium ${isActive ? 'text-textMain' : 'text-textMuted line-through'}`}>{player?.name || 'Unknown'}</p>
          <p className="text-xs text-primary font-semibold">{player?.pos || '--'}</p>
        </div>
      </div>
      
      <button 
        onClick={() => onToggle(player?.name)}
        className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full focus:outline-none focus:ring-2 focus:ring-primary transition-colors ${isActive ? 'bg-accent' : 'bg-gray-600'}`}
      >
        <span aria-hidden="true" className={`pointer-events-none absolute left-0 inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${isActive ? 'translate-x-4' : 'translate-x-0'}`}></span>
      </button>
    </div>
  );
}

function PitchingConfig({ teamId }) {
  const isA = teamId === useMatchupStore(state => state.teamA);
  const fatigue = useMatchupStore(state => isA ? state.fatigueA : state.fatigueB);
  const setFatigue = useMatchupStore(state => isA ? state.setFatigueA : state.setFatigueB);
  const starter = useMatchupStore(state => isA ? state.starterA : state.starterB);
  const setStarter = useMatchupStore(state => isA ? state.setStarterA : state.setStarterB);

  return (
    <div className="mt-6 p-4 bg-background/50 rounded-lg border border-white/5">
      <h4 className="text-sm font-semibold mb-3 border-b border-white/10 pb-2">Pitching Staff ({teamId})</h4>
      
      <div className="mb-4">
        <label className="text-xs text-textMuted block mb-1">Starting Pitcher</label>
        <select 
          value={starter}
          onChange={(e) => setStarter(e.target.value)}
          className="w-full bg-surface border border-white/10 rounded px-2 py-1.5 text-sm text-textMain focus:ring-primary"
        >
          <option>{teamId === 'NYY' ? 'Gerrit Cole (RHP)' : 'Yoshinobu Yamamoto (RHP)'}</option>
          <option>Alternate Starter 1</option>
        </select>
      </div>

      <div>
        <div className="flex justify-between items-center mb-1">
          <label className="text-xs text-textMuted">Bullpen Fatigue</label>
          <span className={`text-xs font-bold ${fatigue > 60 ? 'text-red-400' : 'text-accent'}`}>{fatigue}%</span>
        </div>
        <input 
          type="range" 
          min="0" 
          max="100" 
          value={fatigue}
          onChange={(e) => setFatigue(Number(e.target.value))}
          className="w-full h-1.5 bg-surfaceHover rounded-lg appearance-none cursor-pointer accent-primary"
        />
        <p className="text-[10px] text-textMuted mt-1">
          {fatigue > 60 ? '⚠️ High fatigue: Late innings penalty.' : 'Healthy bullpen.'}
        </p>
      </div>
    </div>
  );
}

export default function LineupBuilder() {
  const { teamA, teamB, inactivePlayersA, inactivePlayersB, togglePlayerA, togglePlayerB } = useMatchupStore();
  const lineupA = MOCK_LINEUPS[teamA] || MOCK_LINEUPS.NYY;
  const lineupB = MOCK_LINEUPS[teamB] || MOCK_LINEUPS.LAD;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      
      <div>
        <h3 className="font-bold text-lg mb-3 flex items-center justify-between">
          Lineup Away
          <span className="text-xs font-normal bg-surfaceHover px-2 py-1 rounded text-textMuted">{teamA}</span>
        </h3>
        <div className="space-y-1">
          {lineupA.map((player, idx) => (
            <BatterRow 
              key={`a-${idx}`} 
              number={idx + 1} 
              player={player} 
              isActive={!inactivePlayersA.includes(player.name)}
              onToggle={togglePlayerA}
            />
          ))}
        </div>
        <PitchingConfig teamId={teamA} />
      </div>

      <div>
        <h3 className="font-bold text-lg mb-3 flex items-center justify-between">
          Lineup Home
          <span className="text-xs font-normal bg-surfaceHover px-2 py-1 rounded text-textMuted">{teamB}</span>
        </h3>
        <div className="space-y-1">
          {lineupB.map((player, idx) => (
            <BatterRow 
              key={`b-${idx}`} 
              number={idx + 1} 
              player={player} 
              isActive={!inactivePlayersB.includes(player.name)}
              onToggle={togglePlayerB}
            />
          ))}
        </div>
        <PitchingConfig teamId={teamB} />
      </div>

    </div>
  );
}
