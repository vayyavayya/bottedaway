export default function WhalePage() {
  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Whale Tracker</h1>
          <p className="text-slate-400">Monitor 5 curated high-performing wallets</p>
        </div>
        <button className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg font-medium">
          Run Check Now
        </button>
      </header>

      <div className="grid grid-cols-2 gap-6">
        <section className="bg-slate-900 rounded-xl p-6 border border-slate-800">
          <h2 className="text-lg font-semibold mb-4">Monitored Wallets</h2>
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="p-3 bg-slate-800/50 rounded-lg flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-slate-700 rounded-full flex items-center justify-center">🐋</div>
                  <div>
                    <div className="font-medium">Whale 0{i}</div>
                    <div className="text-xs text-slate-500 font-mono">4sAU...m5nU</div>
                  </div>
                </div>
                <span className="text-xs bg-slate-700 px-2 py-1 rounded">Active</span>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-slate-900 rounded-xl p-6 border border-slate-800">
          <h2 className="text-lg font-semibold mb-4">Recent Buys (24h)</h2>
          <div className="flex flex-col items-center justify-center py-12 text-slate-500">
            <div className="text-4xl mb-4">📭</div>
            <p>No new buys detected</p>
            <p className="text-sm">Next scan: Tomorrow 9:00 AM</p>
          </div>
        </section>
      </div>
    </div>
  );
}
