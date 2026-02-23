import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mission Control | OpenClaw",
  description: "Unified dashboard for OpenClaw operations",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100">
        <div className="flex h-screen">
          {/* Sidebar */}
          <aside className="w-64 bg-slate-900 border-r border-slate-800 p-4">
            <div className="flex items-center gap-2 mb-8">
              <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold">M</span>
              </div>
              <h1 className="font-bold text-lg">Mission Control</h1>
            </div>
            
            <nav className="space-y-2">
              <NavLink href="/" icon="dashboard">Overview</NavLink>
              <NavLink href="/scanner" icon="radar">Scanner Feed</NavLink>
              <NavLink href="/whale" icon="whale">Whale Tracker</NavLink>
              <NavLink href="/calendar" icon="calendar">Calendar</NavLink>
              <NavLink href="/tasks" icon="board">Tasks</NavLink>
              <NavLink href="/memory" icon="brain">Memory</NavLink>
              <NavLink href="/cost" icon="chart">Cost Dashboard</NavLink>
              <NavLink href="/team" icon="users">Team</NavLink>
            </nav>
          </aside>
          
          {/* Main Content */}
          <main className="flex-1 overflow-auto p-6">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}

function NavLink({ href, icon, children }: { href: string; icon: string; children: React.ReactNode }) {
  const icons: Record<string, string> = {
    dashboard: "◈",
    radar: "◎",
    whale: "🐋",
    calendar: "◴",
    board: "▤",
    brain: "◉",
    chart: "◈",
    users: "👥",
  };
  
  return (
    <a
      href={href}
      className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-800 transition-colors text-slate-400 hover:text-white"
    >
      <span className="text-lg">{icons[icon]}</span>
      <span>{children}</span>
    </a>
  );
}
