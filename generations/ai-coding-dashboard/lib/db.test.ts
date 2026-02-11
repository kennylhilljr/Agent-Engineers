import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock the environment variable
const mockEnv = (url?: string) => {
  if (url) {
    process.env.POSTGRES_URL = url;
  } else {
    delete process.env.POSTGRES_URL;
    delete process.env.DATABASE_URL;
  }
};

// Mock @neondatabase/serverless
vi.mock('@neondatabase/serverless', () => ({
  neon: vi.fn((connectionString: string) => {
    // Return a mock SQL template function
    const mockSql = Object.assign(
      (strings: TemplateStringsArray, ...values: any[]) => {
        return Promise.resolve([{ test: 1 }]);
      },
      {
        connectionString,
      }
    );
    return mockSql;
  }),
}));

// Mock drizzle-orm
vi.mock('drizzle-orm/neon-http', () => ({
  drizzle: vi.fn((sql: any, options: any) => ({
    sql,
    schema: options.schema,
  })),
}));

describe('Database Client - Initialization', () => {
  beforeEach(() => {
    vi.resetModules();
    mockEnv();
  });

  it('should export db instance', async () => {
    mockEnv('postgresql://test:test@localhost:5432/test');
    const { db } = await import('./db');
    expect(db).toBeDefined();
  });

  it('should export schema', async () => {
    mockEnv('postgresql://test:test@localhost:5432/test');
    const { schema } = await import('./db');
    expect(schema).toBeDefined();
    expect(schema.projects).toBeDefined();
    expect(schema.tasks).toBeDefined();
    expect(schema.activityLog).toBeDefined();
  });

  it('should throw error if no database URL is provided', async () => {
    mockEnv(); // No env vars set

    await expect(async () => {
      await import('./db?t=' + Date.now()); // Cache bust
    }).rejects.toThrow();
  });

  it('should use POSTGRES_URL if available', async () => {
    const testUrl = 'postgresql://user:pass@localhost:5432/mydb';
    mockEnv(testUrl);

    const { neon } = await import('@neondatabase/serverless');
    await import('./db?t=' + Date.now());

    expect(neon).toHaveBeenCalledWith(testUrl);
  });

  it('should fallback to DATABASE_URL if POSTGRES_URL not available', async () => {
    delete process.env.POSTGRES_URL;
    const testUrl = 'postgresql://user:pass@localhost:5432/fallback';
    process.env.DATABASE_URL = testUrl;

    const { neon } = await import('@neondatabase/serverless');
    await import('./db?t=' + Date.now());

    expect(neon).toHaveBeenCalledWith(testUrl);
  });
});

describe('Database Client - Connection Testing', () => {
  beforeEach(() => {
    vi.resetModules();
    mockEnv('postgresql://test:test@localhost:5432/test');
  });

  it('should export testConnection function', async () => {
    const { testConnection } = await import('./db');
    expect(testConnection).toBeDefined();
    expect(typeof testConnection).toBe('function');
  });

  it('should return true for successful connection', async () => {
    const { testConnection } = await import('./db');
    const result = await testConnection();
    expect(result).toBe(true);
  });

  it('should return false for failed connection', async () => {
    // Mock a failing connection
    vi.doMock('@neondatabase/serverless', () => ({
      neon: vi.fn(() => {
        const mockSql = () => Promise.reject(new Error('Connection failed'));
        return mockSql;
      }),
    }));

    const { testConnection } = await import('./db?t=' + Date.now());
    const result = await testConnection();
    expect(result).toBe(false);
  });
});

describe('Database Client - Type Safety', () => {
  beforeEach(() => {
    mockEnv('postgresql://test:test@localhost:5432/test');
  });

  it('should have properly typed schema exports', async () => {
    const { schema } = await import('./db');

    // Verify schema has the expected structure
    expect(schema.projects).toBeDefined();
    expect(schema.tasks).toBeDefined();
    expect(schema.activityLog).toBeDefined();
    expect(schema.projectsRelations).toBeDefined();
    expect(schema.tasksRelations).toBeDefined();
    expect(schema.activityLogRelations).toBeDefined();
  });
});
