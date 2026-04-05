import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export default function WinProbabilityChart({ winProbA = 50, winProbB = 50, teamA, teamB }) {
  const data = [
    { name: teamA, value: winProbA },
    { name: teamB, value: winProbB },
  ];

  // Colores sobrios y contrastantes: Azul brillante para A, Naranja ardiente para B
  const COLORS = ['#3B82F6', '#F97316'];

  return (
    <div className="h-64 w-full bg-surfaceHover rounded-xl flex flex-col items-center justify-center p-4 border border-white/5 relative">
      <h3 className="text-sm font-semibold text-textMuted absolute top-3 left-4">Probabilidad de Victoria</h3>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={80}
            paddingAngle={5}
            dataKey="value"
            stroke="none"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip 
            formatter={(value) => [`${value}%`, 'Win Prob']}
            contentStyle={{ backgroundColor: '#1A233A', color: '#F3F4F6', border: 'none', borderRadius: '8px' }}
          />
          <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '12px' }}/>
        </PieChart>
      </ResponsiveContainer>
      
      {/* Etiqueta Central */}
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none mt-2">
        <span className="block text-2xl font-black text-textMain">{Math.max(winProbA, winProbB).toFixed(1)}%</span>
        <span className="block text-[10px] uppercase text-textMuted tracking-wider font-semibold">FAVORITE</span>
      </div>
    </div>
  );
}
