/**
 * PEG Ratio Gauge Visualization
 * Semicircle gauge showing valuation: 0 = günstig (grün), 2+ = teuer (rot)
 */

interface PEGGaugeProps {
  pegRatio: number | null;
}

export function PEGGauge({ pegRatio }: PEGGaugeProps) {
  if (pegRatio === null || pegRatio === undefined) {
    return <div className="text-xs text-[var(--text-muted)]">PEG Ratio nicht verfügbar</div>;
  }

  // Begrenze PEG auf 0-3 für Visualisierung
  const cappedPEG = Math.max(0, Math.min(3, pegRatio));
  const percentage = (cappedPEG / 3) * 100;
  
  // Farbe basierend auf PEG
  const getColor = (peg: number) => {
    if (peg < 1) return "var(--accent-green)";
    if (peg < 2) return "var(--accent-amber)";
    return "var(--accent-red)";
  };

  const getLabel = (peg: number) => {
    if (peg < 1) return "Günstig";
    if (peg < 2) return "Fair";
    return "Teuer";
  };

  const color = getColor(pegRatio);
  const label = getLabel(pegRatio);

  // SVG Gauge
  const radius = 80;
  const strokeWidth = 12;
  const circumference = Math.PI * radius; // Halbkreis
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center space-y-2">
      <svg width="200" height="120" viewBox="0 0 200 120" className="overflow-visible">
        {/* Background Arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="var(--bg-tertiary)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        
        {/* Colored Arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
        
        {/* Center Value */}
        <text
          x="100"
          y="80"
          textAnchor="middle"
          className="text-3xl font-bold"
          fill="var(--text-primary)"
        >
          {pegRatio.toFixed(2)}
        </text>
        
        {/* Label */}
        <text
          x="100"
          y="100"
          textAnchor="middle"
          className="text-xs"
          fill={color}
        >
          {label}
        </text>
      </svg>

      {/* Legend */}
      <div className="flex gap-4 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full bg-[var(--accent-green)]" />
          <span className="text-[var(--text-muted)]">&lt; 1.0 Günstig</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full bg-[var(--accent-amber)]" />
          <span className="text-[var(--text-muted)]">1.0-2.0 Fair</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full bg-[var(--accent-red)]" />
          <span className="text-[var(--text-muted)]">&gt; 2.0 Teuer</span>
        </div>
      </div>

      <p className="text-xs text-[var(--text-muted)] text-center">
        PEG Ratio = P/E ÷ Gewinnwachstum
      </p>
    </div>
  );
}
