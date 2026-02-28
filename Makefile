# ClawBot Memecoin Signal Engine - Makefile
# One-command setup for automated operation

.PHONY: install start stop status logs clean

# Default target - install everything
install:
	@echo "🚀 Installing Memecoin Signal Engine..."
	@bash scripts/setup_launchd.sh
	@echo ""
	@echo "✅ Installation complete!"
	@echo "📅 Runs automatically at 8am and 8pm CET"
	@echo "📝 Logs: logs/memecoin-launchd.log"

# Start the service
start:
	@launchctl load ~/Library/LaunchAgents/com.clawbot.memecoin-signals.plist 2>/dev/null || true
	@echo "✅ Service started"

# Stop the service  
stop:
	@launchctl unload ~/Library/LaunchAgents/com.clawbot.memecoin-signals.plist 2>/dev/null || true
	@echo "✅ Service stopped"

# Check status
status:
	@echo "Service status:"
	@launchctl list | grep memecoin || echo "  Not currently loaded (will auto-load)"
	@echo ""
	@echo "Plist file:"
	@ls -la ~/Library/LaunchAgents/com.clawbot.memecoin-signals.plist 2>/dev/null || echo "  Not installed"
	@echo ""
	@echo "Next runs: 08:00 and 20:00 CET"

# View logs
logs:
	@tail -f logs/memecoin-launchd.log 2>/dev/null || echo "No logs yet. Will appear after first run."

# Run manually now
run-now:
	@echo "🎯 Running memecoin signal scan now..."
	@bash scripts/run_memecoin_signals.sh

# Clean uninstall
clean:
	@launchctl unload ~/Library/LaunchAgents/com.clawbot.memecoin-signals.plist 2>/dev/null || true
	@rm -f ~/Library/LaunchAgents/com.clawbot.memecoin-signals.plist
	@echo "✅ Service uninstalled"

# Help
help:
	@echo "ClawBot Memecoin Signal Engine"
	@echo ""
	@echo "Commands:"
	@echo "  make install    - Install and activate (one-time setup)"
	@echo "  make start      - Start the service"
	@echo "  make stop       - Stop the service"
	@echo "  make status     - Check service status"
	@echo "  make logs       - View live logs"
	@echo "  make run-now    - Run scan immediately"
	@echo "  make clean      - Uninstall service"
	@echo "  make help       - Show this help"
