export default function TasksPage() {
  const columns = [
    { id: "backlog", title: "Backlog", color: "bg-slate-700" },
    { id: "in_progress", title: "In Progress", color: "bg-blue-600" },
    { id: "review", title: "Review", color: "bg-amber-600" },
    { id: "done", title: "Done", color: "bg-green-600" },
  ];

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Tasks Board</h1>
          <p className="text-slate-400">Track work between you and your agents</p>
        </div>
        <button className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg font-medium">
          + New Task
        </button>
      </header>

      <div className="grid grid-cols-4 gap-4">
        {columns.map((col) => (
          <div key={col.id} className="bg-slate-900 rounded-xl p-4 border border-slate-800">
            <div className="flex items-center justify-between mb-4">
              <span className="font-medium">{col.title}</span>
              <span className={`${col.color} text-xs px-2 py-0.5 rounded-full`}>0</span>
            </div>
            <div className="min-h-[200px] flex items-center justify-center text-slate-500 text-sm">
              No tasks
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
