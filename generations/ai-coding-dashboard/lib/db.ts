import { drizzle } from 'drizzle-orm/neon-http';
import { neon } from '@neondatabase/serverless';
import * as schema from '@/db/schema';

/**
 * Database client initialization using Drizzle ORM with Neon serverless
 *
 * Uses POSTGRES_URL environment variable (read-only per app_spec.txt)
 */

// Get the database URL from environment
const databaseUrl = process.env.POSTGRES_URL || process.env.DATABASE_URL;

if (!databaseUrl) {
  throw new Error(
    'POSTGRES_URL or DATABASE_URL environment variable is required for database connection'
  );
}

// Create Neon HTTP client
const sql = neon(databaseUrl);

// Create Drizzle ORM instance with schema
export const db = drizzle(sql, { schema });

/**
 * Helper function to test database connection
 * @returns true if connection is successful, false otherwise
 */
export async function testConnection(): Promise<boolean> {
  try {
    // Simple query to test connection
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
