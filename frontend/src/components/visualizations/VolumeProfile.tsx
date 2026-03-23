/**
 * Volume Profile Chart
 * 20-day volume bar chart with average line
 */

"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

interface VolumeData {
  date: string;
  volume: number;
  close: number;
  change_pct: number;
  color: string;
}

interface VolumeProfileProps {
  ticker: string;
}

export function VolumeProfile({ ticker }: VolumeProfileProps) {
  const [data, setData] = useState<VolumeData[]>([]);
  const [avgVolume, setAvgVolume] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchVolumeData() {
      try {
        setLoading(true);
        const response = await fetch(`http://localhost:8001/api/data/volume-profile/${ticker}`);
        const result = await response.json();
        setData(result.data || []);
        setAvgVolume(result.avg_volume || 0);
      } catch (error) {
        console.error("Volume Profile Fehler:", error);
      } finally {
        setLoading(false);
      }
    }

    if (ticker) {
      fetchVolumeData();
    }
  }, [ticker]);

  if (loading) {
    return <div className="text-xs text-[var(--text-muted)]">Lädt Volumen-Daten...</div>;
  }

  if (!data.length) {
    return <div className="text-xs text-[var(--text-muted)]">Keine Volumen-Daten verfügbar</div>;
  }

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg p-3 shadow-lg">
          <p className="text-xs font-semibold text-[var(--text-primary)] mb-1">
            {new Date(data.date).toLocaleDateString("de-DE", { month: "short", day: "numeric" })}
          </p>
          <p className="text-xs text-[var(--text-secondary)]">
            Volumen: <span className="font-mono font-semibold text-[var(--text-primary)]">
              {(data.volume / 1e6).toFixed(2)}M
            </span>
          </p>
          <p className="text-xs text-[var(--text-secondary)]">
            Kurs: <span className="font-mono text-[var(--text-primary)]">${data.close}</span>
          </p>
          <p className={`text-xs font-semibold ${
            data.change_pct > 0 ? "text-[var(--accent-green)]" : "text-[var(--accent-red)]"
          }`}>
            {data.change_pct > 0 ? "+" : ""}{data.change_pct.toFixed(2)}%
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <p className="text-xs text-[var(--text-secondary)]">
          Ø Volumen: <span className="font-mono font-semibold text-[var(--text-primary)]">
            {(avgVolume / 1e6).toFixed(2)}M
          </span>
        </p>
        <p className="text-xs text-[var(--text-muted)]">Letzte 20 Tage</p>
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.3} />
          <XAxis 
            dataKey="date" 
            tick={{ fontSize: 10, fill: "var(--text-muted)" }}
            tickFormatter={(value) => new Date(value).toLocaleDateString("de-DE", { month: "short", day: "numeric" })}
            angle={-45}
            textAnchor="end"
            height={60}
          />
          <YAxis 
            tick={{ fontSize: 10, fill: "var(--text-muted)" }}
            tickFormatter={(value) => `${(value / 1e6).toFixed(1)}M`}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine 
            y={avgVolume} 
            stroke="var(--accent-amber)" 
            strokeDasharray="3 3" 
            label={{ value: "Ø", position: "right", fontSize: 10, fill: "var(--accent-amber)" }}
          />
          <Bar 
            dataKey="volume" 
            fill="var(--accent-green)"
            radius={[4, 4, 0, 0]}
          >
            {data.map((entry, index) => (
              <Bar 
                key={`bar-${index}`} 
                fill={entry.change_pct > 0 ? "var(--accent-green)" : entry.change_pct < 0 ? "var(--accent-red)" : "var(--text-muted)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
