import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function MarginDistributionChart() {
  // Simulamos los resultados de la Distribución de Skellam para el Dashboard
  const data = [
    { margin: 'A by 3+', prob: 14.6 },
    { margin: 'A by 2', prob: 10.1 },
    { margin: 'A by 1', prob: 11.6 },
    { margin: 'Tie (9th)', prob: 12.1 },
    { margin: 'B by 1', prob: 11.5 },
    { margin: 'B by 2', prob: 9.9 },
    { margin: 'B by 3+', prob: 14.1 }
  ];

  return (
    <div className="h-48 w-full bg-surfaceHover rounded-xl p-4 border border-white/5 relative">
      <h3 className="text-sm font-semibold text-textMuted absolute top-3 left-4">Skellam Margin Distribution</h3>
      <div className="mt-6 h-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
            <XAxis type="number" hide />
            <YAxis dataKey="margin" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#9CA3AF' }} width={60} />
            <Tooltip 
              formatter={(val) => [`${val}%`, 'Prob']}
              cursor={{ fill: '#ffffff10' }}
              contentStyle={{ backgroundColor: '#1A233A', color: '#F3F4F6', border: 'none', borderRadius: '8px' }}
            />
            <Bar dataKey="prob" fill="#10B981" radius={[0, 4, 4, 0]} barSize={12} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
