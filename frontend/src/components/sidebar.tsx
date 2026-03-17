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
} from "lucide-react";
import { useMemo } from "react";

const navItems = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Watchlist", href: "/watchlist", icon: ListChecks },
  { label: "Reports", href: "/reports", icon: FileText },
  { label: "News", href: "/news", icon: Newspaper },
  { label: "Performance", href: "/performance", icon: LineChart },
  { label: "Logs", href: "/logs", icon: Terminal },
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
    <aside className="flex h-screen w-64 flex-col border-r border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-6">
      <div className="mb-8">
        <div className="text-sm uppercase tracking-[0.3em] text-[var(--text-muted)]">KAFIN</div>
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Command</h1>
        <p className="text-xs text-[var(--text-muted)]">Bloomberg Terminal DNA</p>
      </div>

      <nav className="space-y-1">
        {navItems.map(({ label, href, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                active
                  ? "bg-[var(--bg-tertiary)] text-[var(--text-primary)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
              }`}
            >
              <Icon size={18} className="text-inherit" />
              <span>{label}</span>
              {active && (
                <span className="ml-auto h-1 w-1 rounded-full bg-[var(--accent-blue)]" />
              )}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto space-y-3 rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-4 text-xs text-[var(--text-secondary)]">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[var(--accent-green)]" />
          Alle Systeme OK
        </div>
        <div className="flex items-center justify-between text-[var(--text-muted)]">
          <span>Letztes Update</span>
          <span className="text-[var(--text-secondary)]">{lastUpdated}</span>
        </div>
      </div>
    </aside>
  );
}
