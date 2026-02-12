import { describe, it, expect, vi, beforeEach } from "vitest";
import { POST } from "./route";
import { NextRequest } from "next/server";

// Mock the database
vi.mock("@/lib/db", () => ({
  db: {
    select: vi.fn(() => ({
      from: vi.fn(() => ({
        where: vi.fn(() => Promise.resolve([{ id: 1, name: "Test Project" }])),
      })),
    })),
    update: vi.fn(() => ({
      set: vi.fn(() => ({
        where: vi.fn(() => ({
          returning: vi.fn(() =>
            Promise.resolve([
              { id: 1, order: 0, status: "todo" },
            ])
          ),
        })),
      })),
    })),
    insert: vi.fn(() => ({
      values: vi.fn(() => Promise.resolve()),
    })),
  },
}));

// Mock the schema
vi.mock("@/db/schema", () => ({
  projects: {
    id: "id",
  },
  tasks: {
    id: "id",
    projectId: "projectId",
    order: "order",
    status: "status",
  },
  activityLog: {},
}));

// Mock drizzle-orm functions
vi.mock("drizzle-orm", () => ({
  eq: vi.fn(),
  inArray: vi.fn(),
}));

describe("POST /api/projects/[projectId]/tasks/reorder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return error for invalid project ID", async () => {
    const request = new NextRequest("http://localhost/api/projects/abc/tasks/reorder", {
      method: "POST",
      body: JSON.stringify({ taskOrder: [] }),
    });

    const response = await POST(request, { params: { projectId: "abc" } });
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
    expect(data.error).toContain("Invalid project ID");
  });

  it("should return error for invalid request body", async () => {
    const request = new NextRequest("http://localhost/api/projects/1/tasks/reorder", {
      method: "POST",
      body: JSON.stringify({ taskOrder: "not-an-array" }),
    });

    const response = await POST(request, { params: { projectId: "1" } });
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
    expect(data.error).toBe("Invalid request body");
  });

  it("should return error for empty task order array", async () => {
    const request = new NextRequest("http://localhost/api/projects/1/tasks/reorder", {
      method: "POST",
      body: JSON.stringify({ taskOrder: [] }),
    });

    const response = await POST(request, { params: { projectId: "1" } });
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
  });

  it("should validate task order schema", async () => {
    const request = new NextRequest("http://localhost/api/projects/1/tasks/reorder", {
      method: "POST",
      body: JSON.stringify({
        taskOrder: [
          { id: "not-a-number", order: 0 }, // Invalid: id should be number
        ],
      }),
    });

    const response = await POST(request, { params: { projectId: "1" } });
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
  });

  it("should validate task status enum", async () => {
    const request = new NextRequest("http://localhost/api/projects/1/tasks/reorder", {
      method: "POST",
      body: JSON.stringify({
        taskOrder: [
          { id: 1, order: 0, status: "invalid_status" }, // Invalid status
        ],
      }),
    });

    const response = await POST(request, { params: { projectId: "1" } });
    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.success).toBe(false);
  });

  it("should accept valid task reorder request", async () => {
    const { db } = await import("@/lib/db");

    // Mock project exists
    vi.mocked(db.select).mockReturnValueOnce({
      from: vi.fn(() => ({
        where: vi.fn(() => Promise.resolve([{ id: 1, name: "Test Project" }])),
      })),
    } as any);

    // Mock tasks exist
    vi.mocked(db.select).mockReturnValueOnce({
      from: vi.fn(() => ({
        where: vi.fn(() =>
          Promise.resolve([
            { id: 1, projectId: 1, order: 0 },
            { id: 2, projectId: 1, order: 1 },
          ])
        ),
      })),
    } as any);

    const request = new NextRequest("http://localhost/api/projects/1/tasks/reorder", {
      method: "POST",
      body: JSON.stringify({
        taskOrder: [
          { id: 1, order: 1, status: "in_progress" },
          { id: 2, order: 0 },
        ],
      }),
    });

    const response = await POST(request, { params: { projectId: "1" } });
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.success).toBe(true);
  });

  it("should handle status update along with reordering", async () => {
    const { db } = await import("@/lib/db");

    vi.mocked(db.select).mockReturnValue({
      from: vi.fn(() => ({
        where: vi.fn(() =>
          Promise.resolve([
            { id: 1, projectId: 1, order: 0, status: "todo" },
          ])
        ),
      })),
    } as any);

    const request = new NextRequest("http://localhost/api/projects/1/tasks/reorder", {
      method: "POST",
      body: JSON.stringify({
        taskOrder: [{ id: 1, order: 0, status: "done" }],
      }),
    });

    const response = await POST(request, { params: { projectId: "1" } });
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.success).toBe(true);
  });

  it("should log activity event on successful reorder", async () => {
    const { db } = await import("@/lib/db");

    vi.mocked(db.select).mockReturnValue({
      from: vi.fn(() => ({
        where: vi.fn(() =>
          Promise.resolve([
            { id: 1, projectId: 1, order: 0 },
            { id: 2, projectId: 1, order: 1 },
          ])
        ),
      })),
    } as any);

    const insertMock = vi.fn(() => ({
      values: vi.fn(() => Promise.resolve()),
    }));
    vi.mocked(db.insert).mockReturnValue(insertMock() as any);

    const request = new NextRequest("http://localhost/api/projects/1/tasks/reorder", {
      method: "POST",
      body: JSON.stringify({
        taskOrder: [
          { id: 1, order: 1 },
          { id: 2, order: 0 },
        ],
      }),
    });

    await POST(request, { params: { projectId: "1" } });

    // Verify activity log was created
    expect(db.insert).toHaveBeenCalled();
  });
});
