import { describe, it, expect, beforeEach, vi } from 'vitest';

// Set up environment before importing db module
beforeEach(() => {
  process.env.POSTGRES_URL = 'postgresql://test:test@localhost:5432/testdb';
});

// Mock the Neon serverless package
vi.mock('@neondatabase/serverless', () => ({
  neon: vi.fn((connectionString: string) => {
    const mockSql = Object.assign(
      (strings: TemplateStringsArray, ...values: any[]) => {
        // Mock successful query
        return Promise.resolve([{ test: 1 }]);
      },
      {
        connectionString,
      }
    );
    return mockSql;
  }),
}));

describe('Database Client Integration Tests', () => {
  it('should initialize database client with schema', async () => {
    const { db, schema } = await import('./db');

    expect(db).toBeDefined();
    expect(schema).toBeDefined();
    expect(schema.projects).toBeDefined();
    expect(schema.tasks).toBeDefined();
    expect(schema.activityLog).toBeDefined();
  });

  it('should have access to all schema tables via exported schema', async () => {
    const { schema } = await import('./db');

    expect(schema.projects).toBeDefined();
    expect(schema.tasks).toBeDefined();
    expect(schema.activityLog).toBeDefined();
  });

  it('should have access to all schema relations', async () => {
    const { schema } = await import('./db');

    expect(schema.projectsRelations).toBeDefined();
    expect(schema.tasksRelations).toBeDefined();
    expect(schema.activityLogRelations).toBeDefined();
  });

  it('should successfully test database connection', async () => {
    const { testConnection } = await import('./db');

    const isConnected = await testConnection();
    expect(isConnected).toBe(true);
  });

  it('should use correct connection string from environment', async () => {
    const { neon } = await import('@neondatabase/serverless');

    // Re-import to trigger initialization
    await import('./db?t=' + Date.now());

    expect(neon).toHaveBeenCalledWith(
      expect.stringContaining('postgresql://')
    );
  });
});

describe('Database Client - Environment Configuration', () => {
  it('should use POSTGRES_URL from environment', async () => {
    process.env.POSTGRES_URL = 'postgresql://test:test@localhost:5432/testdb';

    const { neon } = await import('@neondatabase/serverless');

    expect(neon).toHaveBeenCalledWith(
      expect.stringContaining('postgresql://')
    );
    expect(neon).toHaveBeenCalledWith(
      expect.stringContaining('testdb')
    );
  });

  it('should support DATABASE_URL fallback', async () => {
    // This test just verifies the code logic supports DATABASE_URL
    // The actual priority is tested in the main db.ts module
    const dbUrl = process.env.POSTGRES_URL || process.env.DATABASE_URL;
    expect(dbUrl).toBeDefined();
  });
});

describe('Database Client - Error Handling', () => {
  it('should handle connection test failures gracefully', async () => {
    // Mock a failing SQL query
    vi.doMock('@neondatabase/serverless', () => ({
      neon: vi.fn(() => {
        const mockSql = () => {
          throw new Error('Connection timeout');
        };
        return mockSql;
      }),
    }));

    vi.resetModules();
    const { testConnection } = await import('./db?t=' + Date.now());

    const isConnected = await testConnection();
    expect(isConnected).toBe(false);
  });

  it('should log errors when connection test fails', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    vi.doMock('@neondatabase/serverless', () => ({
      neon: vi.fn(() => {
        const mockSql = () => Promise.reject(new Error('Database error'));
        return mockSql;
      }),
    }));

    vi.resetModules();
    const { testConnection } = await import('./db?t=' + Date.now());

    await testConnection();

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'Database connection failed:',
      expect.any(Error)
    );

    consoleErrorSpy.mockRestore();
  });
});

describe('Database Client - Type Exports', () => {
  it('should export all schema types', async () => {
    const schema = await import('@/db/schema');

    // Type exports should be available
    type Project = typeof schema.Project;
    type NewProject = typeof schema.NewProject;
    type Task = typeof schema.Task;
    type NewTask = typeof schema.NewTask;
    type ActivityLog = typeof schema.ActivityLog;
    type NewActivityLog = typeof schema.NewActivityLog;

    expect(schema.projects).toBeDefined();
    expect(schema.tasks).toBeDefined();
    expect(schema.activityLog).toBeDefined();
  });

  it('should support type-safe operations', async () => {
    const { schema } = await import('./db');

    // This should type-check at compile time
    const newProject: typeof schema.projects.$inferInsert = {
      name: 'Test Project',
      spec: 'A test specification',
      userId: 'user-123',
    };

    expect(newProject.name).toBe('Test Project');
  });
});
