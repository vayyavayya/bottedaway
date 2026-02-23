export default function ScannerPage() {
  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Scanner Feed</h1>
          <p className="text-slate-400">Live memecoin opportunities from DexScreener & Birdeye</p>
        </div>
        <button className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg font-medium">
          Run Scanner Now
        </button>
      </header>

      <div className="grid grid-cols-3 gap-4">
        <FilterCard title="Market Cap" value="$100K - $500K" />
        <FilterCard title="Age" value="4-10 days" />
        <FilterCard title="Min Liquidity" value="$10,000" />
      </div>

      <section className="bg-slate-900 rounded-xl p-6 border border-slate-800">
        <h2 className="text-lg font-semibold mb-4">Latest Opportunities</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="text-left py-3 text-slate-400 font-medium">Token</th>
                <th className="text-left py-3 text-slate-400 font-medium">Chain</th>
                <th className="text-right py-3 text-slate-400 font-medium">Market Cap</th>
                <th className="text-right py-3 text-slate-400 font-medium">24h Change</th>
                <th className="text-right py-3 text-slate-400 font-medium">Volume</th>
                <th className="text-right py-3 text-slate-400 font-medium">Engines</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              <EmptyState colSpan={6} message="No scanner data yet. Run a scan to populate." />
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function FilterCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
      <div className="text-slate-400 text-sm">{title}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

function EmptyState({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="py-12 text-center text-slate-500">
        {message}
      </td>
    </tr>
  );
}
