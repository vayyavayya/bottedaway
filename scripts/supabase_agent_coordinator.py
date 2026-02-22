#!/usr/bin/env python3
"""
Supabase Agent Coordinator
Multi-agent communication and job queue management
"""

import os
import json
import time
import uuid
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from dataclasses import dataclass

# Supabase client
try:
    from supabase import create_client, Client
except ImportError:
    print("⚠️  supabase-py not installed. Install with: pip install supabase")
    create_client = None

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")  # Use service role key for agents

@dataclass
class AgentJob:
    """Represents a job in the queue."""
    id: str
    job_type: str
    payload: Dict
    status: str
    priority: int
    created_by: str
    assigned_to: Optional[str] = None
    created_at: Optional[str] = None
    result: Optional[Dict] = None

@dataclass
class AgentMessage:
    """Represents a message between agents."""
    id: str
    message_type: str
    from_agent: str
    to_agent: Optional[str]
    subject: str
    content: str
    priority: str
    read: bool
    created_at: str

class SupabaseAgentCoordinator:
    """
    Coordinator for multi-agent system using Supabase backend.
    
    Agents use this to:
    - Claim jobs from queue
    - Send/receive messages
    - Report status
    - Log trades
    """
    
    def __init__(self, agent_id: str, agent_name: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.supabase: Optional[Client] = None
        
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY required.\n"
                "Get these from your Supabase project settings."
            )
        
        if create_client:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Register this agent
        self._register_agent()
    
    def _register_agent(self):
        """Register or update agent in the status table."""
        if not self.supabase:
            return
        
        try:
            data = {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "agent_type": self.agent_type,
                "status": "idle",
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "capabilities": self._get_capabilities()
            }
            
            self.supabase.table("agent_status").upsert(data).execute()
            print(f"✅ Registered agent: {self.agent_name} ({self.agent_id})")
            
        except Exception as e:
            print(f"⚠️  Could not register agent: {e}")
    
    def _get_capabilities(self) -> List[str]:
        """Return agent capabilities based on type."""
        capabilities = {
            "scanner": ["market_scan", "opportunity_detection", "research"],
            "trader": ["trade_execution", "position_management", "risk_management"],
            "researcher": ["deep_research", "sentiment_analysis", "probability_estimation"],
            "reporter": ["reporting", "monitoring", "alerting"],
            "coordinator": ["job_dispatch", "agent_management", "system_monitoring"]
        }
        return capabilities.get(self.agent_type, [])
    
    # ==================== JOB QUEUE ====================
    
    def claim_job(self) -> Optional[AgentJob]:
        """
        Claim the next available job from the queue.
        Returns None if no jobs available.
        """
        if not self.supabase:
            return None
        
        try:
            # Call the claim_next_job function
            result = self.supabase.rpc(
                "claim_next_job",
                {"agent_id": self.agent_id}
            ).execute()
            
            if result.data:
                job_data = result.data[0]
                print(f"🎯 Claimed job: {job_data['job_type']} (priority: {job_data['priority']})")
                
                # Update status to working
                self.update_status("working", job_data['job_id'])
                
                return AgentJob(
                    id=job_data['job_id'],
                    job_type=job_data['job_type'],
                    payload=job_data['payload'],
                    status="assigned",
                    priority=job_data['priority'],
                    created_by="system",  # Will be filled by actual query
                    assigned_to=self.agent_id
                )
            
            return None
            
        except Exception as e:
            print(f"⚠️  Error claiming job: {e}")
            return None
    
    def create_job(
        self,
        job_type: str,
        payload: Dict,
        priority: int = 5,
        target_agent: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a new job in the queue.
        Returns job ID if successful.
        """
        if not self.supabase:
            return None
        
        try:
            data = {
                "job_type": job_type,
                "payload": payload,
                "priority": priority,
                "created_by": self.agent_id,
                "assigned_to": target_agent,
                "status": "pending" if not target_agent else "assigned"
            }
            
            result = self.supabase.table("agent_jobs").insert(data).execute()
            job_id = result.data[0]['id']
            print(f"📋 Created job: {job_type} (ID: {job_id[:8]}...)")
            return job_id
            
        except Exception as e:
            print(f"⚠️  Error creating job: {e}")
            return None
    
    def complete_job(
        self,
        job_id: str,
        success: bool,
        result: Optional[Dict] = None,
        error: Optional[str] = None
    ):
        """Mark a job as completed or failed."""
        if not self.supabase:
            return
        
        try:
            self.supabase.rpc(
                "complete_job",
                {
                    "p_job_id": job_id,
                    "p_success": success,
                    "p_result": result,
                    "p_error": error
                }
            ).execute()
            
            status = "✅ completed" if success else "❌ failed"
            print(f"{status} job: {job_id[:8]}...")
            
            # Update agent status back to idle
            self.update_status("idle")
            
        except Exception as e:
            print(f"⚠️  Error completing job: {e}")
    
    # ==================== MESSAGING ====================
    
    def send_message(
        self,
        to_agent: Optional[str],  # None = broadcast
        subject: str,
        content: str,
        message_type: str = "alert",
        priority: str = "normal",
        payload: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Send a message to another agent or broadcast.
        Returns message ID if successful.
        """
        if not self.supabase:
            return None
        
        try:
            data = {
                "message_type": message_type,
                "from_agent": self.agent_id,
                "to_agent": to_agent,
                "subject": subject,
                "content": content,
                "priority": priority,
                "payload": payload
            }
            
            result = self.supabase.table("agent_messages").insert(data).execute()
            msg_id = result.data[0]['id']
            
            target = f"@{to_agent}" if to_agent else "ALL AGENTS"
            print(f"📨 Message to {target}: {subject}")
            return msg_id
            
        except Exception as e:
            print(f"⚠️  Error sending message: {e}")
            return None
    
    def get_messages(
        self,
        unread_only: bool = True,
        limit: int = 10
    ) -> List[AgentMessage]:
        """Get messages for this agent."""
        if not self.supabase:
            return []
        
        try:
            query = self.supabase.table("agent_messages").select("*")
            
            if unread_only:
                query = query.eq("read", False)
            
            # Messages for this agent OR broadcast (to_agent is null)
            query = query.or_(f"to_agent.eq.{self.agent_id},to_agent.is.null")
            
            result = query.order("created_at", desc=True).limit(limit).execute()
            
            messages = []
            for msg in result.data:
                messages.append(AgentMessage(
                    id=msg['id'],
                    message_type=msg['message_type'],
                    from_agent=msg['from_agent'],
                    to_agent=msg['to_agent'],
                    subject=msg['subject'],
                    content=msg['content'],
                    priority=msg['priority'],
                    read=msg['read'],
                    created_at=msg['created_at']
                ))
            
            return messages
            
        except Exception as e:
            print(f"⚠️  Error getting messages: {e}")
            return []
    
    def mark_message_read(self, message_id: str):
        """Mark a message as read."""
        if not self.supabase:
            return
        
        try:
            self.supabase.table("agent_messages").update({
                "read": True,
                "read_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", message_id).execute()
            
        except Exception as e:
            print(f"⚠️  Error marking message read: {e}")
    
    def broadcast_alert(self, subject: str, content: str, payload: Optional[Dict] = None):
        """Broadcast urgent alert to all agents."""
        return self.send_message(
            to_agent=None,
            subject=subject,
            content=content,
            message_type="alert",
            priority="urgent",
            payload=payload
        )
    
    # ==================== STATUS & HEALTH ====================
    
    def update_status(self, status: str, current_job: Optional[str] = None):
        """Update agent status and heartbeat."""
        if not self.supabase:
            return
        
        try:
            self.supabase.rpc(
                "update_agent_heartbeat",
                {
                    "p_agent_id": self.agent_id,
                    "p_status": status,
                    "p_current_job": current_job
                }
            ).execute()
            
        except Exception as e:
            print(f"⚠️  Error updating status: {e}")
    
    def report_block(self, reason: str):
        """Report that this agent is blocked."""
        if not self.supabase:
            return
        
        try:
            self.supabase.table("agent_status").update({
                "status": "blocked",
                "blocked_reason": reason,
                "blocked_since": datetime.now(timezone.utc).isoformat()
            }).eq("agent_id", self.agent_id).execute()
            
            # Alert coordinator
            self.broadcast_alert(
                subject=f"Agent Blocked: {self.agent_name}",
                content=f"Agent {self.agent_id} is blocked: {reason}",
                payload={"agent_id": self.agent_id, "reason": reason}
            )
            
            print(f"🚨 Reported block: {reason}")
            
        except Exception as e:
            print(f"⚠️  Error reporting block: {e}")
    
    def report_error(self, error: str, context: Optional[Dict] = None):
        """Report an error to the system."""
        print(f"❌ Error reported: {error}")
        
        # Send alert
        self.send_message(
            to_agent="coordinator-main",
            subject=f"Error in {self.agent_name}",
            content=error,
            message_type="alert",
            priority="high",
            payload=context
        )
    
    # ==================== TRADE OPERATIONS ====================
    
    def create_opportunity(
        self,
        market_id: str,
        market_question: str,
        side: str,
        current_price: float,
        confidence: float,
        edge: float,
        research_summary: str,
        suggested_position: float = 5.0,
        expires_hours: int = 6
    ) -> Optional[str]:
        """
        Create a trade opportunity for trader agents.
        Returns opportunity ID.
        """
        if not self.supabase:
            return None
        
        try:
            from datetime import timedelta
            
            data = {
                "market_id": market_id,
                "market_question": market_question,
                "side": side,
                "current_price": current_price,
                "suggested_position": suggested_position,
                "confidence": confidence,
                "edge": edge,
                "research_summary": research_summary,
                "discovered_by": self.agent_id,
                "discovery_method": "perplexity_research",
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
            }
            
            result = self.supabase.table("trade_opportunities").insert(data).execute()
            opp_id = result.data[0]['id']
            
            print(f"💡 Opportunity created: {market_question[:50]}...")
            
            # Create job for trader agent
            self.create_job(
                job_type="execute_trade",
                payload={
                    "opportunity_id": opp_id,
                    "market_id": market_id,
                    "side": side,
                    "amount": suggested_position,
                    "confidence": confidence
                },
                priority=3 if confidence > 0.8 else 5,
                target_agent=None  # Any trader can claim
            )
            
            # Broadcast to all traders
            self.broadcast_alert(
                subject="New Trade Opportunity",
                content=f"{side} {market_question[:60]}... (confidence: {confidence:.0%})",
                payload={"opportunity_id": opp_id, "market_id": market_id}
            )
            
            return opp_id
            
        except Exception as e:
            print(f"⚠️  Error creating opportunity: {e}")
            return None
    
    def log_trade_execution(
        self,
        opportunity_id: Optional[str],
        market_id: str,
        side: str,
        amount: float,
        entry_price: float,
        tx_hash: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> Optional[str]:
        """Log a trade execution."""
        if not self.supabase:
            return None
        
        try:
            data = {
                "opportunity_id": opportunity_id,
                "job_id": job_id,
                "market_id": market_id,
                "side": side,
                "amount": amount,
                "entry_price": entry_price,
                "status": "executed" if tx_hash else "pending",
                "tx_hash": tx_hash,
                "executed_by": self.agent_id,
                "executed_at": datetime.now(timezone.utc).isoformat()
            }
            
            result = self.supabase.table("trade_executions").insert(data).execute()
            exec_id = result.data[0]['id']
            
            print(f"📝 Trade logged: {side} ${amount} on {market_id[:20]}...")
            return exec_id
            
        except Exception as e:
            print(f"⚠️  Error logging trade: {e}")
            return None
    
    # ==================== SYSTEM QUERIES ====================
    
    def get_active_jobs(self) -> List[Dict]:
        """Get all active jobs."""
        if not self.supabase:
            return []
        
        try:
            result = self.supabase.table("v_active_jobs").select("*").execute()
            return result.data
        except Exception as e:
            print(f"⚠️  Error getting active jobs: {e}")
            return []
    
    def get_agent_status(self) -> List[Dict]:
        """Get status of all agents."""
        if not self.supabase:
            return []
        
        try:
            result = self.supabase.table("v_agent_dashboard").select("*").execute()
            return result.data
        except Exception as e:
            print(f"⚠️  Error getting agent status: {e}")
            return []
    
    def get_pending_opportunities(self) -> List[Dict]:
        """Get pending trade opportunities."""
        if not self.supabase:
            return []
        
        try:
            result = self.supabase.table("v_opportunity_pipeline").select("*").execute()
            return result.data
        except Exception as e:
            print(f"⚠️  Error getting opportunities: {e}")
            return []
    
    def get_config(self, key: str) -> Any:
        """Get system configuration value."""
        if not self.supabase:
            return None
        
        try:
            result = self.supabase.table("system_config").select("value").eq("key", key).execute()
            if result.data:
                return result.data[0]['value']
            return None
        except Exception as e:
            print(f"⚠️  Error getting config: {e}")
            return None

# ==================== COORDINATOR AGENT ====================

class CoordinatorAgent(SupabaseAgentCoordinator):
    """
    Special coordinator agent that manages the entire system.
    Monitors health, dispatches jobs, escalates issues.
    """
    
    def __init__(self):
        super().__init__(
            agent_id="coordinator-main",
            agent_name="System Coordinator",
            agent_type="coordinator"
        )
    
    def run_health_check(self):
        """Check health of all agents and system."""
        print("\n🏥 Running health check...")
        
        agents = self.get_agent_status()
        
        stale_agents = []
        blocked_agents = []
        
        for agent in agents:
            health = agent.get('health_status', 'unknown')
            
            if health == 'stale':
                stale_agents.append(agent)
            elif agent.get('status') == 'blocked':
                blocked_agents.append(agent)
        
        # Report issues
        if stale_agents:
            print(f"⚠️  {len(stale_agents)} stale agents detected")
            for agent in stale_agents:
                print(f"   - {agent['agent_name']}: {agent['minutes_since_heartbeat']:.0f}min since heartbeat")
        
        if blocked_agents:
            print(f"🚨 {len(blocked_agents)} blocked agents:")
            for agent in blocked_agents:
                print(f"   - {agent['agent_name']}: {agent.get('blocked_reason', 'Unknown')}")
        
        if not stale_agents and not blocked_agents:
            print("✅ All agents healthy")
        
        # Check for stuck jobs
        active_jobs = self.get_active_jobs()
        old_jobs = [j for j in active_jobs if j.get('age_minutes', 0) > 30]
        
        if old_jobs:
            print(f"⚠️  {len(old_jobs)} jobs stuck for >30 minutes")
        
        return {
            "total_agents": len(agents),
            "stale": len(stale_agents),
            "blocked": len(blocked_agents),
            "stuck_jobs": len(old_jobs)
        }
    
    def dispatch_jobs(self):
        """Ensure pending jobs are dispatched to available agents."""
        print("\n📋 Dispatching jobs...")
        
        opportunities = self.get_pending_opportunities()
        
        # Filter urgent opportunities
        urgent = [o for o in opportunities if o.get('urgency') == 'urgent']
        
        if urgent:
            print(f"🚨 {len(urgent)} urgent opportunities need attention")
            for opp in urgent[:3]:  # Top 3
                print(f"   - {opp['market_question'][:50]}... ({opp['hours_remaining']:.1f}h left)")

# ==================== EXAMPLE USAGE ====================

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 SUPABASE AGENT COORDINATOR")
    print("=" * 60)
    
    # Example: Create a scanner agent
    try:
        scanner = SupabaseAgentCoordinator(
            agent_id="polyclaw-scanner-001",
            agent_name="PolyClaw Market Scanner",
            agent_type="scanner"
        )
        
        # Check for messages
        messages = scanner.get_messages(unread_only=True, limit=5)
        if messages:
            print(f"\n📨 {len(messages)} unread messages")
        
        # Create a test opportunity
        opp_id = scanner.create_opportunity(
            market_id="test-market-123",
            market_question="Will BTC reach $100K in March?",
            side="YES",
            current_price=0.15,
            confidence=0.75,
            edge=0.10,
            research_summary="Bullish sentiment detected"
        )
        
        # Coordinator health check
        coordinator = CoordinatorAgent()
        health = coordinator.run_health_check()
        
        print("\n" + "=" * 60)
        print("Setup complete!")
        
    except ValueError as e:
        print(f"\n⚠️  {e}")
        print("\nTo use Supabase coordination:")
        print("1. Create Supabase project at https://supabase.com")
        print("2. Run the SQL schema from supabase/agent_coordination_schema.sql")
        print("3. Get your project URL and service key")
        print("4. Set environment variables:")
        print("   export SUPABASE_URL='https://your-project.supabase.co'")
        print("   export SUPABASE_SERVICE_KEY='your-service-key'")
        print("5. pip install supabase")
        print("=" * 60)
