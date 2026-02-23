export default function CalendarPage() {
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  
  const jobs = [
    { name: "Memecoin Scanner", schedule: "Every 12h", time: "08:19, 20:19" },
    { name: "Whale Tracker", schedule: "Daily 9am", time: "09:00" },
    { name: "Git Backup", schedule: "Every 2h", time: "Continuous" },
    { name: "Watchlist Maintenance", schedule: "Daily 7am", time: "07:00" },
  ];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold mb-2">Calendar</h1>
        <p className="text-slate-400">Scheduled tasks and cron jobs</p>
      </header>

      <div className="grid grid-cols-7 gap-2">
        {days.map((day) => (
          <div key={day} className="text-center text-sm text-slate-400 py-2">{day}</div>
        ))}
        {Array.from({ length: 28 }, (_, i) => (
          <div
            key={i}
            className={`aspect-square rounded-lg border border-slate-800 p-2 ${
              i === 22 ? "bg-indigo-600/20 border-indigo-600" : "bg-slate-900"
            }`}
          >
            <span className="text-sm">{i + 1}</span>
          </div>
        ))}
      </div>

      <section className="bg-slate-900 rounded-xl p-6 border border-slate-800">
        <h2 className="text-lg font-semibold mb-4">Scheduled Jobs</h2>
        <div className="space-y-3">
          {jobs.map((job) => (
            <div key={job.name} className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
              <div>
                <div className="font-medium">{job.name}</div>
                <div className="text-sm text-slate-400">{job.schedule}</div>
              </div>
              <div className="text-right">
                <div className="text-sm font-mono">{job.time}</div>
                <span className="text-xs bg-green-600/20 text-green-400 px-2 py-0.5 rounded">Active</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
