/**
 * 52-Week Price Range Visualization
 * Horizontal bar showing current price position between 52W low and high
 */

interface PriceRangeBarProps {
  current: number;
  low52w: number;
  high52w: number;
  ticker: string;
}

export function PriceRangeBar({ current, low52w, high52w, ticker }: PriceRangeBarProps) {
  if (!current || !low52w || !high52w) {
    return <div className="text-xs text-[var(--text-muted)]">Keine 52W-Daten verfügbar</div>;
  }

  const range = high52w - low52w;
  const position = ((current - low52w) / range) * 100;
  
  // Farbgradient: rot (0%) → gelb (50%) → grün (100%)
  const getColor = (pos: number) => {
    if (pos < 33) return "var(--accent-red)";
    if (pos < 66) return "var(--accent-amber)";
    return "var(--accent-green)";
  };

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs text-[var(--text-muted)]">
        <span>52W Tief: ${low52w.toFixed(2)}</span>
        <span>52W Hoch: ${high52w.toFixed(2)}</span>
      </div>
      
      {/* Range Bar */}
      <div className="relative h-8 bg-[var(--bg-tertiary)] rounded-lg overflow-hidden">
        {/* Gradient Background */}
        <div 
          className="absolute inset-0 opacity-20"
          style={{
            background: "linear-gradient(to right, var(--accent-red), var(--accent-amber) 50%, var(--accent-green))"
          }}
        />
        
        {/* Current Price Marker */}
        <div
          className="absolute top-0 bottom-0 w-1 transition-all"
          style={{
            left: `${Math.max(0, Math.min(100, position))}%`,
            backgroundColor: getColor(position),
            boxShadow: `0 0 8px ${getColor(position)}`,
          }}
        >
          {/* Price Label */}
          <div 
            className="absolute -top-6 left-1/2 -translate-x-1/2 text-xs font-semibold whitespace-nowrap px-2 py-0.5 rounded"
            style={{ color: getColor(position) }}
          >
            ${current.toFixed(2)}
          </div>
        </div>
      </div>
      
      {/* Position Info */}
      <div className="text-xs text-center text-[var(--text-secondary)]">
        {position < 33 && "Nahe 52W-Tief"}
        {position >= 33 && position < 66 && "Mitte der 52W-Range"}
        {position >= 66 && "Nahe 52W-Hoch"}
        <span className="ml-2 text-[var(--text-muted)]">
          ({position.toFixed(0)}% der Range)
        </span>
      </div>
    </div>
  );
}
