import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { CommandPaletteWrapper } from "@/components/CommandPaletteWrapper";
import { LogViewer } from "@/components/LogViewer";

const inter = Inter({ 
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
  display: "swap",
  fallback: ["system-ui", "sans-serif"]
});

export const metadata: Metadata = {
  title: "Kafin Command Center",
  description: "Bloomberg-grade Earnings Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="de">
      <body className={`${inter.className} bg-[var(--bg-primary)] text-[var(--text-primary)] antialiased`}>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-y-auto bg-[var(--bg-primary)]">
            <div className="mx-auto max-w-7xl p-8">{children}</div>
          </main>
        </div>
      <CommandPaletteWrapper />
      <LogViewer />
    </body>
  </html>
  );
}
