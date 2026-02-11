import type { Config } from 'drizzle-kit';

/**
 * Drizzle Kit configuration for migrations
 *
 * This configuration is used by drizzle-kit for:
 * - Generating migrations from schema changes
 * - Pushing schema to database
 * - Managing database migrations
 */
export default {
  schema: './db/schema.ts',
  out: './drizzle',
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.POSTGRES_URL || process.env.DATABASE_URL || '',
  },
  verbose: true,
  strict: true,
} satisfies Config;
