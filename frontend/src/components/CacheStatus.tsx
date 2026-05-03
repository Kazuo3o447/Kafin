"use client";

type Props = {
  fromCache: boolean;
  ageSeconds: number | null;
  onRefresh: () => void;
  refreshing: boolean;
};

export function CacheStatus({ fromCache, ageSeconds, onRefresh, refreshing }: Props) {
  return (
    <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
      {fromCache && ageSeconds !== null ? (
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          Daten aus Cache · vor {ageSeconds < 60 ? `${ageSeconds}s` : `${Math.floor(ageSeconds / 60)}min`}
        </span>
      ) : (
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
          Frische Daten
        </span>
      )}
      <button
        onClick={onRefresh}
        disabled={refreshing}
        className="underline hover:no-underline disabled:opacity-50"
      >
        {refreshing ? "Lädt..." : "Aktualisieren"}
      </button>
    </div>
  );
}
