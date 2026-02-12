import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TaskCard } from "./task-card";
import { TaskResponse } from "@/lib/api-types";

// Mock dnd-kit sortable hook
vi.mock("@dnd-kit/sortable", () => ({
  useSortable: vi.fn(() => ({
    attributes: {},
    listeners: {},
    setNodeRef: vi.fn(),
    transform: null,
    transition: null,
    isDragging: false,
  })),
}));

describe("TaskCard", () => {
  const mockTask: TaskResponse = {
    id: 1,
    projectId: 1,
    category: "frontend",
    description: "Build login page",
    steps: ["Create form", "Add validation", "Style with Tailwind"],
    status: "todo",
    order: 0,
    agentNotes: "Use React Hook Form for validation",
  };

  it("should render task description", () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText("Build login page")).toBeInTheDocument();
  });

  it("should render category badge", () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText("frontend")).toBeInTheDocument();
  });

  it("should render step count", () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText("3 steps")).toBeInTheDocument();
  });

  it("should render agent notes when present", () => {
    render(<TaskCard task={mockTask} />);
    expect(
      screen.getByText("Use React Hook Form for validation")
    ).toBeInTheDocument();
  });

  it("should not render agent notes when not present", () => {
    const taskWithoutNotes = { ...mockTask, agentNotes: null };
    render(<TaskCard task={taskWithoutNotes} />);
    expect(
      screen.queryByText("Use React Hook Form for validation")
    ).not.toBeInTheDocument();
  });

  it("should not render step count when task has no steps", () => {
    const taskWithoutSteps = { ...mockTask, steps: [] };
    render(<TaskCard task={taskWithoutSteps} />);
    expect(screen.queryByText(/steps/)).not.toBeInTheDocument();
  });

  it("should apply correct category color for frontend", () => {
    render(<TaskCard task={mockTask} />);
    const badge = screen.getByText("frontend");
    expect(badge).toHaveClass("bg-blue-600");
  });

  it("should apply correct category color for backend", () => {
    const backendTask = { ...mockTask, category: "backend" };
    render(<TaskCard task={backendTask} />);
    const badge = screen.getByText("backend");
    expect(badge).toHaveClass("bg-green-600");
  });

  it("should apply correct category color for testing", () => {
    const testingTask = { ...mockTask, category: "testing" };
    render(<TaskCard task={testingTask} />);
    const badge = screen.getByText("testing");
    expect(badge).toHaveClass("bg-yellow-600");
  });

  it("should apply correct category color for deployment", () => {
    const deploymentTask = { ...mockTask, category: "deployment" };
    render(<TaskCard task={deploymentTask} />);
    const badge = screen.getByText("deployment");
    expect(badge).toHaveClass("bg-purple-600");
  });

  it("should apply correct category color for documentation", () => {
    const docsTask = { ...mockTask, category: "documentation" };
    render(<TaskCard task={docsTask} />);
    const badge = screen.getByText("documentation");
    expect(badge).toHaveClass("bg-pink-600");
  });

  it("should apply default category color for unknown category", () => {
    const unknownTask = { ...mockTask, category: "unknown" };
    render(<TaskCard task={unknownTask} />);
    const badge = screen.getByText("unknown");
    expect(badge).toHaveClass("bg-gray-600");
  });

  it("should apply loading styles when isLoading is true", () => {
    const { container } = render(<TaskCard task={mockTask} isLoading />);
    const card = container.querySelector(".pointer-events-none");
    expect(card).toBeInTheDocument();
  });

  it("should render drag handle icon", () => {
    render(<TaskCard task={mockTask} />);
    const dragHandle = screen.getByLabelText("Drag handle");
    expect(dragHandle).toBeInTheDocument();
  });

  it("should apply dragging opacity when isDragging is true", () => {
    const { container } = render(<TaskCard task={mockTask} isDragging />);
    const card = container.firstChild as HTMLElement;
    expect(card).toHaveStyle({ opacity: 0.5 });
  });
});
