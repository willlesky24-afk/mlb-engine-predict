import React from 'react';
import useMatchupStore from '../../store/useMatchupStore';

const TEAMS = [
  { id: 'NYY', name: 'New York Yankees' },
  { id: 'LAD', name: 'Los Angeles Dodgers' },
  { id: 'HOU', name: 'Houston Astros' },
  { id: 'ATL', name: 'Atlanta Braves' },
  { id: 'BAL', name: 'Baltimore Orioles' },
  { id: 'PHI', name: 'Philadelphia Phillies' },
];

export default function MatchupSelector() {
  const { teamA, teamB, setTeamA, setTeamB } = useMatchupStore();
  return (
    <div className="flex flex-col md:flex-row items-center gap-4 bg-background/50 p-4 rounded-lg border border-white/5">
      <div className="flex-1 w-full">
        <label className="block text-sm font-semibold text-textMuted mb-2">Away Team (Equipo A)</label>
        <select 
          value={teamA}
          onChange={(e) => setTeamA(e.target.value)}
          className="w-full bg-surface border border-white/10 rounded-md py-2 px-3 text-textMain focus:outline-none focus:ring-2 focus:ring-primary transition-all"
        >
          {TEAMS.map(team => (
            <option key={`a-${team.id}`} value={team.id}>{team.name}</option>
          ))}
        </select>
      </div>

      <div className="flex items-center justify-center shrink-0 w-12 h-12 bg-surfaceHover rounded-full font-bold text-textMuted border border-white/5 text-sm">
        VS
      </div>

      <div className="flex-1 w-full">
        <label className="block text-sm font-semibold text-textMuted mb-2">Home Team (Equipo B)</label>
        <select 
          value={teamB}
          onChange={(e) => setTeamB(e.target.value)}
          className="w-full bg-surface border border-white/10 rounded-md py-2 px-3 text-textMain focus:outline-none focus:ring-2 focus:ring-primary transition-all"
        >
          {TEAMS.map(team => (
            <option key={`b-${team.id}`} value={team.id}>{team.name}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
