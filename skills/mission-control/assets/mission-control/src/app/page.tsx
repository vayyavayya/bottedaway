import { db } from "@/db";
import { scannerResults, whaleBuys, tasks, costLogs } from "@/db/schema";
import { desc, eq, sql } from "drizzle-orm";
import { formatDistanceToNow } from "date-fns";

export default async function Dashboard() {
  // Fetch latest data
  const latestScans = await db
    .select()
    .from(scannerResults)
    .orderBy(desc(scannerResults.timestamp))
    .limit(5);

  const recentWhaleBuys = await db
    .select()
    .from(whaleBuys)
    .orderBy(desc(whaleBuys.timestamp))
    .limit(5);

  const openTasks = await db
    .select()
    .from(tasks)
    .where(eq(tasks.status, "in_progress"))
    .limit(5);

  const todayCost = await db
    .select({ total: sql<number>`sum(${costLogs.costUsd})` })
    .from(costLogs)
    .where(sql<number>`date(${costLogs.timestamp}) = date('now')`);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold mb-2">Overview</h1>
        <p className="text-slate-400">
          Welcome back. Here's what's happening with your OpenClaw operations.
        </p>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="Today's Scans"
          value={latestScans.length}
          subtitle="8 opportunities found"
          trend="+2"
          trendUp={true}
        />
        <StatCard
          title="Whale Activity"
          value={recentWhaleBuys.length}
          subtitle="New buys detected"
          trend="+1"
          trendUp={true}
        />
        <StatCard
          title="Open Tasks"
          value={openTasks.length}
          subtitle="In progress"
          trend="0"
          trendUp={null}
        />
        <StatCard
          title="Today's Cost"
          value={`$${(todayCost[0]?.total || 0).toFixed(2)}`}
          subtitle="API usage"
          trend="-12%"
          trendUp={true}
        />
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-2 gap-6">
        <section className="bg-slate-900 rounded-xl p-6 border border-slate-800">
          <h2 className="text-lg font-semibold mb-4">Recent Scanner Finds</h2>
          <div className="space-y-3">
            {latestScans.map((scan) => (
              <div
                key={scan.id}
                className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg"
              >
                <div>
                  <div className="font-medium">{scan.tokenSymbol}</div>
                  <div className="text-sm text-slate-400">
                    MC: ${(scan.marketCap || 0).toLocaleString()}
                  </div>
                </div>
                <div className="text-right">
                  <div
                    className={`font-mono ${
                      (scan.change24h || 0) >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {scan.change24h > 0 ? "+" : ""}
                    {scan.change24h?.toFixed(1)}%
                  </div>
                  <div className="text-xs text-slate-500">
                    {formatDistanceToNow(scan.timestamp || new Date(), { addSuffix: true })}
                  </div>
                </div>
              </div>
            ))}
            {latestScans.length === 0 && (
              <p className="text-slate-500 text-center py-8">No scans yet. Run a scanner sweep to populate.</p>
            )}
          </div>
        </section>

        <section className="bg-slate-900 rounded-xl p-6 border border-slate-800">
          <h2 className="text-lg font-semibold mb-4">Whale Tracker Activity</h2>
          <div className="space-y-3">
            {recentWhaleBuys.map((buy) => (
              <div
                key={buy.id}
                className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg"
              >
                <div>
                  <div className="font-medium">{buy.tokenSymbol}</div>
                  <div className="text-sm text-slate-400">
                    Wallet #{buy.walletId}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-indigo-400">
                    Score: {buy.score?.toFixed(1)}
                  </div>
                  <div className="text-xs text-slate-500">
                    {formatDistanceToNow(buy.timestamp || new Date(), { addSuffix: true })}
                  </div>
                </div>
              </div>
            ))}
            {recentWhaleBuys.length === 0 && (
              <p className="text-slate-500 text-center py-8">No whale activity yet. Daily scan runs at 9am.</p>
            )}
          </div>
        </section>
      </div>

      {/* Quick Actions */}
      <section className="bg-slate-900 rounded-xl p-6 border border-slate-800">
        <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
        <div className="flex gap-3">
          <button className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg font-medium transition-colors">
            Run Scanner Now
          </button>
          <button className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg font-medium transition-colors">
            Check Whale Wallets
          </button>
          <button className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg font-medium transition-colors">
            Sync Git Backup
          </button>
          <button className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg font-medium transition-colors">
            View Cost Report
          </button>
        </div>
      </section>
    </div>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  trend,
  trendUp,
}: {
  title: string;
  value: string | number;
  subtitle: string;
  trend: string;
  trendUp: boolean | null;
}) {
  return (
    <div className="bg-slate-900 rounded-xl p-6 border border-slate-800">
      <div className="text-slate-400 text-sm mb-1">{title}</div>
      <div className="text-3xl font-bold mb-1">{value}</div>
      <div className="flex items-center gap-2">
        <span className="text-slate-500 text-sm">{subtitle}</span>
        {trendUp !== null && (
          <span
            className={`text-xs ${
              trendUp ? "text-green-400" : "text-red-400"
            }`}
          >
            {trendUp ? "↑" : "↓"} {trend}
          </span>
        )}
      </div>
    </div>
  );
}
