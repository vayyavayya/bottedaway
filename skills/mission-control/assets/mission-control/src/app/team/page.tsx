export default function TeamPage() {
  const agents = [
    {
      name: "nadeshan",
      role: "Primary Assistant",
      avatar: "🤖",
      status: "working",
      task: "Mission Control development",
      skills: ["trading", "infrastructure", "automation"],
    },
  ];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold mb-2">Team</h1>
        <p className="text-slate-400">Your digital organization</p>
      </header>

      <div className="grid grid-cols-3 gap-6">
        {agents.map((agent) => (
          <div key={agent.name} className="bg-slate-900 rounded-xl p-6 border border-slate-800">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center text-3xl">
                {agent.avatar}
              </div>
              <div>
                <div className="font-bold text-lg">{agent.name}</div>
                <div className="text-slate-400">{agent.role}</div>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    agent.status === "working" ? "bg-green-500" : "bg-slate-500"
                  }`}
                />
                <span className="text-sm capitalize">{agent.status}</span>
              </div>
              
              <div className="text-sm text-slate-400">
                Current: {agent.task}
              </div>

              <div className="flex flex-wrap gap-2 mt-3">
                {agent.skills.map((skill) => (
                  <span key={skill} className="text-xs bg-slate-800 px-2 py-1 rounded">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
