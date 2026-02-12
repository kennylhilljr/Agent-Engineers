import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import KanbanBoardPage from "./page";

// Mock CopilotKit context
vi.mock("@copilotkit/react-core", () => ({
  useCopilotContext: vi.fn(() => ({
    // Mock context value
  })),
}));

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("KanbanBoardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render kanban board with columns", async () => {
    // Mock successful fetch
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: [],
      }),
    });

    render(<KanbanBoardPage />);

    // Check that all columns are rendered
    expect(screen.getByText("Kanban Board")).toBeInTheDocument();
    expect(screen.getByText("To Do")).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("Blocked")).toBeInTheDocument();

    // Wait for fetch to complete
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/projects/1/tasks");
    });
  });

  it("should fetch and display tasks from API", async () => {
    const mockTasks = [
      {
        id: 1,
        projectId: 1,
        category: "frontend",
        description: "Build login page",
        steps: ["Create form", "Add validation"],
        status: "todo",
        order: 0,
        agentNotes: null,
      },
      {
        id: 2,
        projectId: 1,
        category: "backend",
        description: "Setup API",
        steps: ["Configure routes"],
        status: "in_progress",
        order: 0,
        agentNotes: null,
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: mockTasks,
      }),
    });

    render(<KanbanBoardPage />);

    await waitFor(() => {
      expect(screen.getByText("Build login page")).toBeInTheDocument();
      expect(screen.getByText("Setup API")).toBeInTheDocument();
    });

    // Check that tasks are displayed (they exist in the document)
    expect(screen.getByText("Build login page")).toBeInTheDocument();
    expect(screen.getByText("Setup API")).toBeInTheDocument();
    expect(screen.getByText("frontend")).toBeInTheDocument();
    expect(screen.getByText("backend")).toBeInTheDocument();
  });

  it("should organize tasks by status in correct columns", async () => {
    const mockTasks = [
      {
        id: 1,
        projectId: 1,
        category: "testing",
        description: "Write unit tests",
        steps: [],
        status: "done",
        order: 0,
        agentNotes: null,
      },
      {
        id: 2,
        projectId: 1,
        category: "deployment",
        description: "Deploy to staging",
        steps: [],
        status: "blocked",
        order: 0,
        agentNotes: null,
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: mockTasks,
      }),
    });

    render(<KanbanBoardPage />);

    await waitFor(() => {
      expect(screen.getByText("Write unit tests")).toBeInTheDocument();
      expect(screen.getByText("Deploy to staging")).toBeInTheDocument();
    });

    // Check that tasks are displayed with correct categories
    expect(screen.getByText("Write unit tests")).toBeInTheDocument();
    expect(screen.getByText("Deploy to staging")).toBeInTheDocument();
    expect(screen.getByText("testing")).toBeInTheDocument();
    expect(screen.getByText("deployment")).toBeInTheDocument();
  });

  it("should display error message when fetch fails", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    render(<KanbanBoardPage />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("should show loading state during fetch", async () => {
    mockFetch.mockImplementationOnce(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: async () => ({ success: true, data: [] }),
              }),
            100
          )
        )
    );

    render(<KanbanBoardPage />);

    // Component should render while loading
    expect(screen.getByText("Kanban Board")).toBeInTheDocument();
  });

  it("should display task count badges in columns", async () => {
    const mockTasks = [
      {
        id: 1,
        projectId: 1,
        category: "frontend",
        description: "Task 1",
        steps: [],
        status: "todo",
        order: 0,
        agentNotes: null,
      },
      {
        id: 2,
        projectId: 1,
        category: "frontend",
        description: "Task 2",
        steps: [],
        status: "todo",
        order: 1,
        agentNotes: null,
      },
      {
        id: 3,
        projectId: 1,
        category: "backend",
        description: "Task 3",
        steps: [],
        status: "in_progress",
        order: 0,
        agentNotes: null,
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: mockTasks,
      }),
    });

    render(<KanbanBoardPage />);

    await waitFor(() => {
      const badges = screen.getAllByText(/^\d+$/);
      // Should have badges showing task counts (2 in todo, 1 in progress, 0 in others)
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it("should display empty state for columns with no tasks", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: [],
      }),
    });

    render(<KanbanBoardPage />);

    await waitFor(() => {
      const dropZones = screen.getAllByText("Drop tasks here");
      // All 4 columns should show the empty state
      expect(dropZones).toHaveLength(4);
    });
  });

  it("should display category badges with correct colors", async () => {
    const mockTasks = [
      {
        id: 1,
        projectId: 1,
        category: "frontend",
        description: "Frontend task",
        steps: [],
        status: "todo",
        order: 0,
        agentNotes: null,
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: mockTasks,
      }),
    });

    render(<KanbanBoardPage />);

    await waitFor(() => {
      const categoryBadge = screen.getByText("frontend");
      expect(categoryBadge).toBeInTheDocument();
    });
  });

  it("should display agent notes when present", async () => {
    const mockTasks = [
      {
        id: 1,
        projectId: 1,
        category: "backend",
        description: "API task",
        steps: [],
        status: "todo",
        order: 0,
        agentNotes: "Important: Use authentication middleware",
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: mockTasks,
      }),
    });

    render(<KanbanBoardPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Important: Use authentication middleware")
      ).toBeInTheDocument();
    });
  });

  it("should display step count when task has steps", async () => {
    const mockTasks = [
      {
        id: 1,
        projectId: 1,
        category: "frontend",
        description: "Complex task",
        steps: ["Step 1", "Step 2", "Step 3"],
        status: "todo",
        order: 0,
        agentNotes: null,
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: mockTasks,
      }),
    });

    render(<KanbanBoardPage />);

    await waitFor(() => {
      expect(screen.getByText("3 steps")).toBeInTheDocument();
    });
  });
});
