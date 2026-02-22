-- Supabase Agent Coordination Schema
-- Multi-agent system for PolyClaw trading

-- Enable realtime for all tables
alter publication supabase_realtime add table agent_jobs;
alter publication supabase_realtime add table agent_messages;
alter publication supabase_realtime add table agent_status;
alter publication supabase_realtime add table trade_opportunities;
alter publication supabase_realtime add table trade_executions;

-- ============================================
-- 1. AGENT JOB QUEUE
-- ============================================
create table agent_jobs (
    id uuid default gen_random_uuid() primary key,
    job_type text not null, -- 'scan_markets', 'execute_trade', 'research', 'report'
    payload jsonb not null, -- Job parameters
    status text default 'pending', -- 'pending', 'assigned', 'in_progress', 'completed', 'failed'
    priority integer default 5, -- 1 (highest) to 10 (lowest)
    
    -- Agent assignment
    created_by text not null, -- Agent ID that created the job
    assigned_to text, -- Agent ID assigned to execute
    
    -- Timestamps
    created_at timestamp with time zone default now(),
    assigned_at timestamp with time zone,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    
    -- Results
    result jsonb,
    error_message text,
    
    -- Constraints
    constraint valid_status check (status in ('pending', 'assigned', 'in_progress', 'completed', 'failed')),
    constraint valid_priority check (priority between 1 and 10)
);

-- Indexes for performance
create index idx_agent_jobs_status on agent_jobs(status);
create index idx_agent_jobs_assigned on agent_jobs(assigned_to);
create index idx_agent_jobs_priority on agent_jobs(priority, created_at);
create index idx_agent_jobs_type on agent_jobs(job_type);

-- ============================================
-- 2. AGENT-TO-AGENT MESSAGING
-- ============================================
create table agent_messages (
    id uuid default gen_random_uuid() primary key,
    message_type text not null, -- 'command', 'alert', 'status', 'result'
    
    -- Routing
    from_agent text not null,
    to_agent text, -- null = broadcast to all
    
    -- Content
    subject text not null,
    content text not null,
    payload jsonb, -- Additional data
    
    -- Priority & status
    priority text default 'normal', -- 'low', 'normal', 'high', 'urgent'
    read boolean default false,
    
    -- Timestamps
    created_at timestamp with time zone default now(),
    read_at timestamp with time zone,
    
    -- Constraints
    constraint valid_priority check (priority in ('low', 'normal', 'high', 'urgent'))
);

-- Indexes
create index idx_agent_messages_to on agent_messages(to_agent, read);
create index idx_agent_messages_from on agent_messages(from_agent, created_at);
create index idx_agent_messages_priority on agent_messages(priority, created_at);

-- ============================================
-- 3. AGENT STATUS & HEARTBEAT
-- ============================================
create table agent_status (
    agent_id text primary key,
    agent_name text not null,
    agent_type text not null, -- 'scanner', 'trader', 'researcher', 'reporter', 'coordinator'
    
    -- Status
    status text default 'idle', -- 'idle', 'working', 'blocked', 'error', 'offline'
    current_job uuid references agent_jobs(id),
    
    -- Health
    last_heartbeat timestamp with time zone default now(),
    last_activity timestamp with time zone default now(),
    
    -- Capabilities & load
    capabilities jsonb default '[]', -- ['market_scan', 'trade_execution', 'research']
    current_load integer default 0, -- Number of active jobs
    max_load integer default 5,
    
    -- Metrics
    jobs_completed integer default 0,
    jobs_failed integer default 0,
    total_profit numeric(20, 8) default 0,
    
    -- Blocking
    blocked_reason text,
    blocked_since timestamp with time zone,
    
    -- Metadata
    config jsonb default '{}',
    version text,
    
    -- Constraints
    constraint valid_agent_status check (status in ('idle', 'working', 'blocked', 'error', 'offline'))
);

-- Indexes
create index idx_agent_status_status on agent_status(status);
create index idx_agent_status_heartbeat on agent_status(last_heartbeat);
create index idx_agent_status_type on agent_status(agent_type);

-- ============================================
-- 4. TRADE OPPORTUNITIES (Scanner → Trader)
-- ============================================
create table trade_opportunities (
    id uuid default gen_random_uuid() primary key,
    
    -- Market info
    market_id text not null,
    market_question text not null,
    platform text default 'polymarket', -- 'polymarket', 'kalshi', etc.
    
    -- Trade details
    side text not null, -- 'YES' or 'NO'
    current_price numeric(10, 4) not null,
    target_price numeric(10, 4),
    suggested_position numeric(10, 2),
    
    -- Analysis
    confidence numeric(5, 4), -- 0.0 to 1.0
    edge numeric(10, 4), -- Expected edge vs market
    research_summary text,
    
    -- Source
    discovered_by text not null, -- Agent ID
    discovery_method text, -- 'perplexity_research', 'smart_money', 'hedge_scan'
    
    -- Status
    status text default 'pending', -- 'pending', 'approved', 'rejected', 'expired'
    
    -- Timestamps
    discovered_at timestamp with time zone default now(),
    expires_at timestamp with time zone, -- Opportunity window
    reviewed_by text,
    reviewed_at timestamp with time zone,
    
    -- Constraints
    constraint valid_side check (side in ('YES', 'NO')),
    constraint valid_opp_status check (status in ('pending', 'approved', 'rejected', 'expired'))
);

-- Indexes
create index idx_opportunities_status on trade_opportunities(status);
create index idx_opportunities_market on trade_opportunities(market_id);
create index idx_opportunities_expires on trade_opportunities(expires_at);

-- ============================================
-- 5. TRADE EXECUTION LOG
-- ============================================
create table trade_executions (
    id uuid default gen_random_uuid() primary key,
    opportunity_id uuid references trade_opportunities(id),
    job_id uuid references agent_jobs(id),
    
    -- Execution details
    market_id text not null,
    side text not null,
    amount numeric(10, 2) not null,
    entry_price numeric(10, 4) not null,
    
    -- Results
    status text default 'pending', -- 'pending', 'executed', 'failed', 'settled'
    tx_hash text,
    exit_price numeric(10, 4),
    pnl numeric(10, 2),
    
    -- Agents
    executed_by text not null,
    
    -- Timestamps
    created_at timestamp with time zone default now(),
    executed_at timestamp with time zone,
    settled_at timestamp with time zone,
    
    -- Constraints
    constraint valid_exec_status check (status in ('pending', 'executed', 'failed', 'settled'))
);

-- Indexes
create index idx_executions_status on trade_executions(status);
create index idx_executions_opportunity on trade_executions(opportunity_id);
create index idx_executions_executed_by on trade_executions(executed_by);

-- ============================================
-- 6. AGENT PERFORMANCE METRICS
-- ============================================
create table agent_performance (
    id uuid default gen_random_uuid() primary key,
    agent_id text not null references agent_status(agent_id),
    period text not null, -- 'daily', 'weekly', 'monthly'
    period_start date not null,
    
    -- Metrics
    jobs_completed integer default 0,
    jobs_failed integer default 0,
    trades_executed integer default 0,
    trades_profitable integer default 0,
    total_pnl numeric(20, 8) default 0,
    avg_trade_size numeric(10, 2),
    avg_confidence numeric(5, 4),
    
    -- Efficiency
    avg_job_duration interval,
    uptime_minutes integer default 0,
    
    created_at timestamp with time zone default now()
);

-- Indexes
create index idx_performance_agent on agent_performance(agent_id, period_start);

-- ============================================
-- 7. SYSTEM CONFIGURATION
-- ============================================
create table system_config (
    key text primary key,
    value jsonb not null,
    description text,
    updated_at timestamp with time zone default now(),
    updated_by text
);

-- Default configs
insert into system_config (key, value, description) values
    ('trading_enabled', 'true', 'Master switch for trading'),
    ('max_daily_exposure', '20', 'Maximum daily trading volume in USD'),
    ('max_position_size', '5', 'Maximum position size in USD'),
    ('min_edge_threshold', '0.10', 'Minimum edge required for trade'),
    ('risk_mode', 'normal', 'Current risk mode: conservative, normal, aggressive'),
    ('scanner_interval_minutes', '240', 'How often scanner runs'),
    ('coordinator_agent', 'coordinator-main', 'Primary coordinator agent ID');

-- ============================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================

-- Enable RLS on all tables
alter table agent_jobs enable row level security;
alter table agent_messages enable row level security;
alter table agent_status enable row level security;
alter table trade_opportunities enable row level security;
alter table trade_executions enable row level security;

-- Allow all operations for now (agents use service role key)
-- In production, you'd restrict by agent_id

create policy "Allow all" on agent_jobs for all using (true);
create policy "Allow all" on agent_messages for all using (true);
create policy "Allow all" on agent_status for all using (true);
create policy "Allow all" on trade_opportunities for all using (true);
create policy "Allow all" on trade_executions for all using (true);

-- ============================================
-- FUNCTIONS FOR AGENT COORDINATION
-- ============================================

-- Function to claim next available job
CREATE OR REPLACE FUNCTION claim_next_job(agent_id text)
RETURNS TABLE (
    job_id uuid,
    job_type text,
    payload jsonb,
    priority integer
) AS $$
BEGIN
    RETURN QUERY
    WITH next_job AS (
        SELECT aj.id
        FROM agent_jobs aj
        WHERE aj.status = 'pending'
        ORDER BY aj.priority, aj.created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE agent_jobs aj
    SET 
        status = 'assigned',
        assigned_to = agent_id,
        assigned_at = now()
    FROM next_job
    WHERE aj.id = next_job.id
    RETURNING aj.id, aj.job_type, aj.payload, aj.priority;
END;
$$ LANGUAGE plpgsql;

-- Function to update agent heartbeat
CREATE OR REPLACE FUNCTION update_agent_heartbeat(
    p_agent_id text,
    p_status text,
    p_current_job uuid DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    INSERT INTO agent_status (agent_id, status, current_job, last_heartbeat, last_activity)
    VALUES (p_agent_id, p_status, p_current_job, now(), now())
    ON CONFLICT (agent_id)
    DO UPDATE SET
        status = p_status,
        current_job = p_current_job,
        last_heartbeat = now(),
        last_activity = CASE WHEN p_status = 'working' THEN now() ELSE agent_status.last_activity END;
END;
$$ LANGUAGE plpgsql;

-- Function to report job completion
CREATE OR REPLACE FUNCTION complete_job(
    p_job_id uuid,
    p_success boolean,
    p_result jsonb DEFAULT NULL,
    p_error text DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    UPDATE agent_jobs
    SET 
        status = CASE WHEN p_success THEN 'completed' ELSE 'failed' END,
        result = p_result,
        error_message = p_error,
        completed_at = now()
    WHERE id = p_job_id;
    
    -- Update agent status
    UPDATE agent_status
    SET 
        status = 'idle',
        current_job = NULL,
        jobs_completed = CASE WHEN p_success THEN jobs_completed + 1 ELSE jobs_completed END,
        jobs_failed = CASE WHEN NOT p_success THEN jobs_failed + 1 ELSE jobs_failed END
    WHERE current_job = p_job_id;
END;
$$ LANGUAGE plpgsql;

-- Function to broadcast message to all agents
CREATE OR REPLACE FUNCTION broadcast_message(
    p_from_agent text,
    p_subject text,
    p_content text,
    p_payload jsonb DEFAULT NULL,
    p_priority text DEFAULT 'normal'
)
RETURNS void AS $$
BEGIN
    INSERT INTO agent_messages (from_agent, to_agent, subject, content, payload, priority)
    VALUES (p_from_agent, NULL, p_subject, p_content, p_payload, p_priority);
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VIEWS FOR MONITORING
-- ============================================

-- Active jobs view
create view v_active_jobs as
select 
    aj.*,
    extract(epoch from (now() - aj.created_at))/60 as age_minutes
from agent_jobs aj
where aj.status in ('pending', 'assigned', 'in_progress')
order by aj.priority, aj.created_at;

-- Agent dashboard view
create view v_agent_dashboard as
select 
    ags.*,
    extract(epoch from (now() - ags.last_heartbeat))/60 as minutes_since_heartbeat,
    case 
        when ags.last_heartbeat < now() - interval '5 minutes' then 'stale'
        when ags.last_heartbeat < now() - interval '2 minutes' then 'warning'
        else 'healthy'
    end as health_status
from agent_status ags
order by ags.last_heartbeat desc;

-- Opportunity pipeline view
create view v_opportunity_pipeline as
select 
    topp.*,
    extract(epoch from (topp.expires_at - now()))/3600 as hours_remaining,
    case 
        when topp.expires_at < now() then 'expired'
        when topp.expires_at < now() + interval '1 hour' then 'urgent'
        when topp.expires_at < now() + interval '6 hours' then 'soon'
        else 'normal'
    end as urgency
from trade_opportunities topp
where topp.status = 'pending'
order by topp.confidence desc, topp.discovered_at;

-- Performance summary view
create view v_daily_performance as
select 
    date_trunc('day', te.executed_at) as day,
    te.executed_by as agent_id,
    count(*) as trades,
    sum(case when te.pnl > 0 then 1 else 0 end) as winners,
    sum(case when te.pnl < 0 then 1 else 0 end) as losers,
    sum(te.pnl) as total_pnl,
    avg(te.pnl) as avg_pnl,
    sum(te.amount) as volume
from trade_executions te
where te.status = 'settled'
group by 1, 2
order by 1 desc, 2;
