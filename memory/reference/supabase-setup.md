# Supabase Setup Guide

Setting up Supabase for AI Operating System dashboard.

---

## Step 1: Create Supabase Project

1. Go to https://supabase.com
2. Create new project
3. Choose strong database password (save in 1Password/secure location)
4. Select region: Frankfurt (eu-central-1) closest to Europe/Berlin
5. Wait for project to spin up

---

## Step 2: Database Schema

Run this SQL in Supabase SQL Editor:

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- TASKS TABLE
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    status TEXT CHECK (status IN ('backlog', 'todo', 'in_progress', 'done')),
    priority TEXT CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    assignee TEXT,
    project_id UUID REFERENCES projects(id),
    due_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- PROJECTS TABLE
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    status TEXT CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    description TEXT,
    progress INTEGER CHECK (progress >= 0 AND progress <= 100),
    start_date DATE,
    target_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- CONTENT TABLE
CREATE TABLE content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT,
    body TEXT,
    status TEXT CHECK (status IN ('idea', 'draft', 'scheduled', 'published')),
    platform TEXT[], -- array: ['twitter', 'linkedin', 'youtube']
    scheduled_date TIMESTAMPTZ,
    published_url TEXT,
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- DOCUMENTS TABLE
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT,
    type TEXT CHECK (type IN ('meeting_notes', 'sop', 'reference', 'brief')),
    tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AUTO-UPDATE updated_at TRIGGER
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_updated_at BEFORE UPDATE ON content
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## Step 3: Row Level Security (RLS)

```sql
-- Enable RLS on all tables
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE content ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "Service role can do everything" ON tasks
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can do everything" ON projects
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can do everything" ON content
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can do everything" ON documents
    FOR ALL USING (auth.role() = 'service_role');

-- Allow authenticated users
CREATE POLICY "Authenticated users can read all" ON tasks
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can read all" ON projects
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can read all" ON content
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can read all" ON documents
    FOR SELECT USING (auth.role() = 'authenticated');
```

---

## Step 4: API Credentials

After setup, collect:

1. **Project URL**: `https://xxxxxx.supabase.co`
2. **Anon Key**: Settings → API → `anon public`
3. **Service Role Key**: Settings → API → `service_role` (keep secret!)

---

## Step 5: Agent Integration

Add to `memory/reference/api-reference.md`:

```
## Supabase (Dashboard DB)

- URL: https://YOUR-PROJECT.supabase.co/rest/v1/
- Auth: Bearer service_role_key
- Headers: 
  - apikey: YOUR_ANON_KEY
  - Authorization: Bearer YOUR_SERVICE_ROLE_KEY
  - Content-Type: application/json
- Tables: tasks, projects, content, documents
```

---

## Next Steps

1. [ ] Create Supabase project
2. [ ] Run SQL schema
3. [ ] Enable RLS
4. [ ] Store credentials securely
5. [ ] Build Lovable dashboard
6. [ ] Connect agent to Supabase

---

*Created: 2026-02-14*
