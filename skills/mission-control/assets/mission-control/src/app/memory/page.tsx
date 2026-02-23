export default function MemoryPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold mb-2">Memory Browser</h1>
        <p className="text-slate-400">Searchable history of all decisions, scans, and events</p>
      </header>

      <div className="relative">
        <input
          type="text"
          placeholder="Search memories..."
          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-4 py-3 text-white placeholder:text-slate-500"
        />
      </div>

      <div className="space-y-4">
        <MemoryCard
          date="2026-02-22"
          category="infrastructure"
          content="Discord migration completed. Bot connected, 5 channels created, whale tracker activated with 5 wallets."
          tags={["discord", "migration", "whale-tracker"]}
        />
        <MemoryCard
          date="2026-02-22"
          category="trading"
          content="Scanner found 8 opportunities. Notable: ORAMAMA at -68.7% dip with $3.6M volume (possible accumulation)."
          tags={["scanner", "memecoin", "dip-entry"]}
        />
      </div>
    </div>
  );
}

function MemoryCard({ date, category, content, tags }: { 
  date: string; 
  category: string; 
  content: string; 
  tags: string[];
}) {
  const categoryColors: Record<string, string> = {
    infrastructure: "bg-blue-600/20 text-blue-400",
    trading: "bg-green-600/20 text-green-400",
    decision: "bg-amber-600/20 text-amber-400",
    learning: "bg-purple-600/20 text-purple-400",
  };

  return (
    <div className="bg-slate-900 rounded-xl p-6 border border-slate-800">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-slate-500 text-sm">{date}</span>
        <span className={`text-xs px-2 py-0.5 rounded ${categoryColors[category] || "bg-slate-700"}`}>
          {category}
        </span>
      </div>
      
      <p className="mb-3">{content}</p>
      
      <div className="flex gap-2">
        {tags.map((tag) => (
          <span key={tag} className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-400">
            #{tag}
          </span>
        ))}
      </div>
    </div>
  );
}
