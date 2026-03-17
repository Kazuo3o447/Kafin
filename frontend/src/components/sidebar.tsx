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
    <aside className="flex h-screen w-72 flex-col border-r border-[var(--border)] bg-[var(--bg-secondary)] px-6 py-8">
      <div className="mb-12">
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Kafin</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">Trading Intelligence</p>
      </div>

      <nav className="space-y-2">
        {navItems.map(({ label, href, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`group flex items-center gap-4 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 ${
                active
                  ? "bg-[var(--accent-blue)] text-white shadow-md"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
              }`}
            >
              <Icon size={20} className={active ? "text-white" : "text-[var(--text-muted)]"} />
              <span className="flex-1">{label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto space-y-4 rounded-xl border border-[var(--border)] bg-[var(--bg-tertiary)] p-5 text-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent-green)] bg-opacity-10">
            <span className="h-2 w-2 rounded-full bg-[var(--accent-green)]" />
          </div>
          <div>
            <div className="font-medium text-[var(--text-primary)]">System Online</div>
            <div className="text-xs text-[var(--text-muted)]">Alle Services verfügbar</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
