import { drizzle } from 'drizzle-orm/neon-http';
import { neon } from '@neondatabase/serverless';
import * as schema from '@/db/schema';

/**
 * Database client initialization using Drizzle ORM with Neon serverless
 *
 * Uses POSTGRES_URL environment variable (read-only per app_spec.txt)
 */

// Get the database URL from environment (lazy initialization to avoid crashing at import time)
const databaseUrl = process.env.POSTGRES_URL || process.env.DATABASE_URL;

function getSQL() {
  const url = process.env.POSTGRES_URL || process.env.DATABASE_URL;
  if (!url) {
    throw new Error(
      'POSTGRES_URL or DATABASE_URL environment variable is required for database connection'
    );
  }
  return neon(url);
}

// Create Neon HTTP client and Drizzle instance lazily
let _db: ReturnType<typeof drizzle> | null = null;

export function getDb() {
  if (!_db) {
    const sql = getSQL();
    _db = drizzle(sql, { schema });
  }
  return _db;
}

// For backward compatibility - uses a proxy to defer initialization
export const db = new Proxy({} as ReturnType<typeof drizzle>, {
  get(_target, prop) {
    return (getDb() as any)[prop];
  },
});

/**
 * Helper function to test database connection
 * @returns true if connection is successful, false otherwise
 */
export async function testConnection(): Promise<boolean> {
  try {
    const sql = getSQL();
    await sql`SELECT 1 as test`;
    return true;
  } catch (error) {
    console.error('Database connection failed:', error);
    return false;
  }
}

/**
 * Export schema for easy access
 */
export { schema };
