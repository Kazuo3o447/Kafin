"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  ListChecks,
  FileText,
  Newspaper,
  LineChart,
  Terminal,
  Settings,
  CalendarDays,
  Search,
  Activity,
} from "lucide-react";
import { useMemo } from "react";

const navItems = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Watchlist", href: "/watchlist", icon: ListChecks },
  { label: "Earnings-Radar", href: "/earnings", icon: CalendarDays },
  { label: "Reports", href: "/reports", icon: FileText },
  { label: "News", href: "/news", icon: Newspaper },
  { label: "Performance", href: "/performance", icon: LineChart },
  { label: "Status", href: "/status", icon: Activity },
  { label: "Einstellungen", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const lastUpdated = useMemo(() => {
    return new Date().toLocaleTimeString("de-DE", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }, []);

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col
                      border-r border-[var(--border)]
                      bg-[var(--bg-secondary)]
                      px-3 py-5 relative z-10">

      {/* Logo */}
      <div className="mb-6 px-2 flex items-center gap-2.5">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center
                        rounded-lg bg-[var(--accent-blue)]
                        shadow-lg shadow-blue-500/30">
          <span className="text-xs font-bold text-white">K</span>
        </div>
        <div>
          <p className="text-sm font-bold text-[var(--text-primary)]
                        tracking-widest">KAFIN</p>
          <p className="text-[9px] text-[var(--text-muted)]
                        uppercase tracking-[0.25em]">Intelligence</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5">
        {navItems.map(({ label, href, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`relative flex items-center gap-3 rounded-xl
                          px-3 py-2.5 text-xs font-medium
                          transition-all duration-150 ${
                active
                  ? "bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {/* Aktiver Indikator — linke Linie */}
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2
                                 h-5 w-0.5 rounded-r-full
                                 bg-[var(--accent-blue)]" />
              )}
              <Icon
                size={15}
                className={active
                  ? "text-[var(--accent-blue)]"
                  : "text-[var(--text-muted)]"}
              />
              <span className="flex-1 truncate">{label}</span>
            </Link>
          );
        })}
        
        {/* Terminal - Opens in new window */}
        <a
          href="/terminal"
          target="_blank"
          rel="noopener noreferrer"
          className="relative flex items-center gap-3 rounded-xl
                     px-3 py-2.5 text-xs font-medium
                     transition-all duration-150
                     text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
        >
          <Terminal
            size={15}
            className="text-[var(--text-muted)]"
          />
          <span className="flex-1 truncate">Terminal</span>
        </a>
      </nav>

      {/* Schnellsuche */}
      <div className="mt-3 mb-3">
        <button
          onClick={() => {
            window.dispatchEvent(new CustomEvent("open-command-palette"));
          }}
          className="flex w-full items-center gap-2.5 rounded-xl
                     border border-[var(--border)] px-3 py-2
                     text-xs text-[var(--text-muted)]
                     transition-all duration-150
                     hover:bg-[var(--bg-tertiary)]
                     hover:text-[var(--text-secondary)]"
        >
          <Search size={13} />
          <span className="flex-1 text-left">Suche</span>
          <kbd className="rounded bg-[var(--bg-tertiary)] px-1.5 py-0.5
                          text-[9px] font-mono
                          border border-[var(--border)]">⌘K</kbd>
        </button>
      </div>

      {/* System-Status */}
      <div className="rounded-xl border border-[var(--border)]
                      bg-[var(--bg-tertiary)] px-3 py-3">
        <div className="flex items-center gap-2.5">
          {/* Pulsierender grüner Punkt */}
          <div className="relative flex h-2 w-2 shrink-0">
            <span className="absolute inline-flex h-full w-full
                             animate-ping rounded-full
                             bg-[var(--accent-green)] opacity-60" />
            <span className="relative inline-flex h-2 w-2
                             rounded-full bg-[var(--accent-green)]" />
          </div>
          <div>
            <p className="text-xs font-medium text-[var(--text-primary)]">
              Online
            </p>
            <p className="text-[10px] text-[var(--text-muted)]">
              Alle Services aktiv
            </p>
          </div>
        </div>
      </div>

    </aside>
  );
}
