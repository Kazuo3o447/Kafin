"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * /journal leitet weiter auf Performance → Tab "Meine Trades".
 * Die Journal-Funktionalität ist in Performance integriert (Tab 3).
 *
 * Diese Seite bleibt als Route erhalten damit bestehende Links/Bookmarks
 * nicht brechen — sie leitet sofort weiter ohne sichtbares Flackern.
 */
export default function JournalRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/performance?tab=my_trades");
  }, [router]);

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex items-center
                    justify-center">
      <p className="text-sm text-[var(--text-muted)]">
        Weiterleitung zu Performance → Meine Trades…
      </p>
    </div>
  );
}
