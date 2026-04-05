import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function PredictedScoreBar({ scoreA = 4.5, scoreB = 4.0, teamA, teamB }) {
  const data = [
    { name: teamA, runs: scoreA },
    { name: teamB, runs: scoreB },
  ];

  const COLORS = ['#3B82F6', '#F97316'];

  return (
    <div className="h-48 w-full bg-surfaceHover rounded-xl p-4 border border-white/5 relative">
      <h3 className="text-sm font-semibold text-textMuted absolute top-3 left-4">Proyección de Carreras</h3>
      <div className="mt-6 h-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 20, right: 20, left: -20, bottom: 5 }}>
            <XAxis dataKey="name" stroke="#9CA3AF" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
            <Tooltip 
              cursor={{ fill: '#ffffff10' }}
              contentStyle={{ backgroundColor: '#1A233A', color: '#F3F4F6', border: 'none', borderRadius: '8px' }}
            />
            <Bar dataKey="runs" radius={[4, 4, 0, 0]}>
               {data.map((entry, index) => (
                <Cell key={`bar-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
