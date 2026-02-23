export default function CostPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold mb-2">Cost Dashboard</h1>
        <p className="text-slate-400">API usage and spending tracking</p>
      </header>

      <div className="grid grid-cols-4 gap-4">
        <StatCard title="Today" value="$0.00" change="-12%" />
        <StatCard title="This Week" value="$0.00" change="0%" />
        <StatCard title="This Month" value="$0.00" change="-5%" />
        <StatCard title="Projected" value="$5-10" change="On target" />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <section className="bg-slate-900 rounded-xl p-6 border border-slate-800">
          <h2 className="text-lg font-semibold mb-4">Model Usage</h2>
          <div className="space-y-4">
            <ModelRow
              name="kimi-coding/k2p5"
              tokens="55k"
              cost="$0.00"
              percent={95}
              color="bg-indigo-600"
            />
            <ModelRow
              name="minimax-portal/MiniMax-M2.5"
              tokens="0"
              cost="$0.00"
              percent={0}
              color="bg-amber-600"
            />
          </div>
        </section>

        <section className="bg-slate-900 rounded-xl p-6 border border-slate-800">
          <h2 className="text-lg font-semibold mb-4">Cost Optimization</h2>
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-3">
              <span className="text-green-400">✓</span>
              <span>Cron jobs use free models (Gemini Flash Lite)</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-green-400">✓</span>
              <span>Local Llama 3.2 for heartbeats ($0)</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-green-400">✓</span>
              <span>Kimi K2.5 flat rate for routine work</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-amber-400">⚡</span>
              <span>MiniMax reserved for high-reasoning tasks</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function StatCard({ title, value, change }: { title: string; value: string; change: string }) {
  return (
    <div className="bg-slate-900 rounded-xl p-6 border border-slate-800">
      <div className="text-slate-400 text-sm mb-1">{title}</div>
      <div className="text-2xl font-bold mb-1">{value}</div>
      <div className="text-xs text-green-400">{change}</div>
    </div>
  );
}

function ModelRow({ name, tokens, cost, percent, color }: { 
  name: string; 
  tokens: string; 
  cost: string; 
  percent: number;
  color: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="font-medium">{name}</span>
        <div className="text-sm text-slate-400">
          {tokens} tokens · {cost}
        </div>
      </div>
      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
