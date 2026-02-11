'use client';

import { useState } from 'react';

export default function DatabaseSchemaDemo() {
  const [activeTab, setActiveTab] = useState<'schema' | 'types' | 'config'>('schema');

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            KAN-49: PostgreSQL + Drizzle ORM
          </h1>
          <p className="text-slate-300">
            Database schema setup with Drizzle ORM and Neon serverless PostgreSQL
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {(['schema', 'types', 'config'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-6 py-3 rounded-lg font-semibold transition-all ${
                activeTab === tab
                  ? 'bg-purple-600 text-white shadow-lg'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              {tab === 'schema' && 'Schema Tables'}
              {tab === 'types' && 'TypeScript Types'}
              {tab === 'config' && 'Configuration'}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="bg-slate-800 rounded-xl p-6 shadow-2xl">
          {activeTab === 'schema' && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-white mb-4">Database Tables</h2>

              {/* Projects Table */}
              <div className="bg-slate-900 rounded-lg p-6 border-2 border-purple-500">
                <h3 className="text-xl font-semibold text-purple-400 mb-4">
                  📊 projects
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div className="font-bold text-white">Column</div>
                    <div className="font-bold text-white">Type</div>
                    <div className="font-bold text-white">Constraints</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>id</div>
                    <div>serial</div>
                    <div>PRIMARY KEY</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>name</div>
                    <div>text</div>
                    <div>NOT NULL</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>spec</div>
                    <div>text</div>
                    <div>NOT NULL</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>preferred_layout</div>
                    <div>text</div>
                    <div>DEFAULT 'kanban'</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>created_at</div>
                    <div>timestamp</div>
                    <div>DEFAULT NOW(), NOT NULL</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>user_id</div>
                    <div>text</div>
                    <div>NOT NULL</div>
                  </div>
                </div>
              </div>

              {/* Tasks Table */}
              <div className="bg-slate-900 rounded-lg p-6 border-2 border-green-500">
                <h3 className="text-xl font-semibold text-green-400 mb-4">
                  ✅ tasks
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div className="font-bold text-white">Column</div>
                    <div className="font-bold text-white">Type</div>
                    <div className="font-bold text-white">Constraints</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>id</div>
                    <div>serial</div>
                    <div>PRIMARY KEY</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>project_id</div>
                    <div>integer</div>
                    <div>FK → projects.id, NOT NULL</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>category</div>
                    <div>text</div>
                    <div>NOT NULL</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>description</div>
                    <div>text</div>
                    <div>NOT NULL</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>steps</div>
                    <div>jsonb</div>
                    <div>NOT NULL (string[])</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>status</div>
                    <div>text</div>
                    <div>DEFAULT 'todo', NOT NULL</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>agent_notes</div>
                    <div>text</div>
                    <div>NULLABLE</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>order</div>
                    <div>integer</div>
                    <div>DEFAULT 0, NOT NULL</div>
                  </div>
                </div>
              </div>

              {/* Activity Log Table */}
              <div className="bg-slate-900 rounded-lg p-6 border-2 border-blue-500">
                <h3 className="text-xl font-semibold text-blue-400 mb-4">
                  📝 activity_log
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div className="font-bold text-white">Column</div>
                    <div className="font-bold text-white">Type</div>
                    <div className="font-bold text-white">Constraints</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>id</div>
                    <div>serial</div>
                    <div>PRIMARY KEY</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>project_id</div>
                    <div>integer</div>
                    <div>FK → projects.id, NOT NULL</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>event_type</div>
                    <div>text</div>
                    <div>NOT NULL</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>event_data</div>
                    <div>jsonb</div>
                    <div>NOT NULL (Record)</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>agent_reasoning</div>
                    <div>text</div>
                    <div>NULLABLE</div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 font-mono text-slate-300">
                    <div>timestamp</div>
                    <div>timestamp</div>
                    <div>DEFAULT NOW(), NOT NULL</div>
                  </div>
                </div>
              </div>

              {/* Relationships */}
              <div className="bg-slate-900 rounded-lg p-6 border-2 border-yellow-500">
                <h3 className="text-xl font-semibold text-yellow-400 mb-4">
                  🔗 Relationships
                </h3>
                <div className="space-y-3 text-slate-300">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-purple-400">projects</span>
                    <span>→</span>
                    <span className="font-mono text-green-400">tasks</span>
                    <span className="text-sm">(one-to-many, cascade delete)</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-purple-400">projects</span>
                    <span>→</span>
                    <span className="font-mono text-blue-400">activity_log</span>
                    <span className="text-sm">(one-to-many, cascade delete)</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'types' && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-white mb-4">TypeScript Types</h2>

              <div className="space-y-4">
                <div className="bg-slate-900 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-purple-400 mb-3">Project Types</h3>
                  <pre className="text-sm text-slate-300 overflow-x-auto">
{`type Project = {
  id: number;
  name: string;
  spec: string;
  preferredLayout: string | null;
  createdAt: Date;
  userId: string;
}

type NewProject = {
  name: string;
  spec: string;
  preferredLayout?: string;
  userId: string;
}`}
                  </pre>
                </div>

                <div className="bg-slate-900 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-green-400 mb-3">Task Types</h3>
                  <pre className="text-sm text-slate-300 overflow-x-auto">
{`type Task = {
  id: number;
  projectId: number;
  category: string;
  description: string;
  steps: string[];
  status: string;
  agentNotes: string | null;
  order: number;
}

type NewTask = {
  projectId: number;
  category: string;
  description: string;
  steps: string[];
  status?: string;
  agentNotes?: string;
  order?: number;
}`}
                  </pre>
                </div>

                <div className="bg-slate-900 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-blue-400 mb-3">ActivityLog Types</h3>
                  <pre className="text-sm text-slate-300 overflow-x-auto">
{`type ActivityLog = {
  id: number;
  projectId: number;
  eventType: string;
  eventData: Record<string, any>;
  agentReasoning: string | null;
  timestamp: Date;
}

type NewActivityLog = {
  projectId: number;
  eventType: string;
  eventData: Record<string, any>;
  agentReasoning?: string;
}`}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'config' && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-white mb-4">Configuration Files</h2>

              <div className="space-y-4">
                <div className="bg-slate-900 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-purple-400 mb-3">
                    📄 drizzle.config.ts
                  </h3>
                  <pre className="text-sm text-slate-300 overflow-x-auto">
{`import type { Config } from 'drizzle-kit';

export default {
  schema: './db/schema.ts',
  out: './drizzle',
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.POSTGRES_URL ||
         process.env.DATABASE_URL || '',
  },
  verbose: true,
  strict: true,
} satisfies Config;`}
                  </pre>
                </div>

                <div className="bg-slate-900 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-green-400 mb-3">
                    📄 lib/db.ts
                  </h3>
                  <pre className="text-sm text-slate-300 overflow-x-auto">
{`import { drizzle } from 'drizzle-orm/neon-http';
import { neon } from '@neondatabase/serverless';
import * as schema from '@/db/schema';

const databaseUrl = process.env.POSTGRES_URL ||
                   process.env.DATABASE_URL;

const sql = neon(databaseUrl);
export const db = drizzle(sql, { schema });

export async function testConnection() {
  try {
    await sql\`SELECT 1 as test\`;
    return true;
  } catch (error) {
    console.error('Database connection failed:', error);
    return false;
  }
}`}
                  </pre>
                </div>

                <div className="bg-slate-900 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-blue-400 mb-3">
                    📦 Package Scripts
                  </h3>
                  <div className="space-y-2 text-sm text-slate-300">
                    <div className="flex items-start gap-3">
                      <code className="bg-slate-800 px-2 py-1 rounded">db:generate</code>
                      <span>Generate migrations from schema</span>
                    </div>
                    <div className="flex items-start gap-3">
                      <code className="bg-slate-800 px-2 py-1 rounded">db:migrate</code>
                      <span>Run pending migrations</span>
                    </div>
                    <div className="flex items-start gap-3">
                      <code className="bg-slate-800 px-2 py-1 rounded">db:push</code>
                      <span>Push schema changes directly</span>
                    </div>
                    <div className="flex items-start gap-3">
                      <code className="bg-slate-800 px-2 py-1 rounded">db:studio</code>
                      <span>Open Drizzle Studio UI</span>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-900 rounded-lg p-6 border-2 border-green-500">
                  <h3 className="text-lg font-semibold text-green-400 mb-3">
                    ✅ Dependencies Installed
                  </h3>
                  <div className="space-y-2 text-sm text-slate-300">
                    <div className="flex items-center gap-3">
                      <span className="text-green-400">✓</span>
                      <code>drizzle-orm</code>
                      <span className="text-slate-500">^0.45.1</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-green-400">✓</span>
                      <code>drizzle-kit</code>
                      <span className="text-slate-500">^0.31.9</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-green-400">✓</span>
                      <code>@neondatabase/serverless</code>
                      <span className="text-slate-500">^1.0.2</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Test Results */}
        <div className="mt-8 bg-green-900/50 border-2 border-green-500 rounded-xl p-6">
          <h2 className="text-2xl font-bold text-green-400 mb-4">✅ Test Results</h2>
          <div className="space-y-2 text-slate-200">
            <div className="flex items-center gap-3">
              <span className="text-green-400 font-bold">58 tests passing</span>
            </div>
            <div className="text-sm space-y-1">
              <div>• db/schema.test.ts - 22 tests</div>
              <div>• db/schema.integration.test.ts - 16 tests</div>
              <div>• lib/db.test.ts - 9 tests</div>
              <div>• lib/db.integration.test.ts - 11 tests</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
