"use client";

import dynamic from "next/dynamic";

const InteractiveChart = dynamic(
  () => import("@/components/InteractiveChart"),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[420px] items-center justify-center
                      rounded-xl border border-[var(--border)]
                      bg-[var(--bg-secondary)]">
        <p className="text-sm text-[var(--text-muted)]">
          Lade Chart...
        </p>
      </div>
    ),
  }
);

export default function ChartWrapper({ ticker }: { ticker: string }) {
  return <InteractiveChart ticker={ticker} />;
}
