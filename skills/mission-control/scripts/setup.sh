#!/bin/bash
# Mission Control Setup Script
# Run this to initialize the entire NextJS app

set -e

echo "🦞 Setting up Mission Control..."

MC_DIR="$HOME/.openclaw/workspace/skills/mission-control/assets/mission-control"
mkdir -p "$MC_DIR"
cd "$MC_DIR"

# Create NextJS app structure
echo "📁 Creating directories..."
mkdir -p src/{app,components,db,lib}
mkdir -p src/components/{ui,dashboard}
mkdir -p src/app/{scanner,whale,calendar,cost,memory,tasks,team}

# Initialize package.json if not exists
if [ ! -f package.json ]; then
echo "📦 Initializing package.json..."
cat > package.json << 'EOF'
{
  "name": "mission-control",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "db:push": "drizzle-kit push:sqlite",
    "db:studio": "drizzle-kit studio"
  },
  "dependencies": {
    "next": "14.1.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "drizzle-orm": "^0.29.3",
    "better-sqlite3": "^9.4.1",
    "tailwindcss": "^3.4.1",
    "lucide-react": "^0.312.0",
    "recharts": "^2.10.4",
    "date-fns": "^3.3.1",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.1"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "@types/node": "^20.11.5",
    "@types/react": "^18.2.48",
    "@types/better-sqlite3": "^7.6.8",
    "drizzle-kit": "^0.20.14",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.33"
  }
}
EOF
fi

# Create tsconfig.json
cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
EOF

# Create next.config.js
cat > next.config.js << 'EOF'
/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: { serverActions: true }
}
module.exports = nextConfig
EOF

# Create drizzle.config.ts
cat > drizzle.config.ts << 'EOF'
import type { Config } from "drizzle-kit";

export default {
  schema: "./src/db/schema.ts",
  out: "./drizzle",
  driver: "better-sqlite",
  dbCredentials: { url: "./data/mission-control.db" },
} satisfies Config;
EOF

echo "✅ Project structure created!"
echo ""
echo "Next steps:"
echo "1. cd $MC_DIR"
echo "2. npm install"
echo "3. npm run db:push"
echo "4. npm run dev"
