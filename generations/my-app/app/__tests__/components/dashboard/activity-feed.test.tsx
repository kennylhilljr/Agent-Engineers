import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ActivityFeed, ActivityEvent } from "@/components/dashboard/activity-feed";

describe("ActivityFeed", () => {
  const mockEvents: ActivityEvent[] = [
    {
      id: "1",
      type: "file_modified",
      title: "File updated",
      description: "Modified component.tsx",
      timestamp: new Date(Date.now() - 1000 * 60 * 5), // 5 minutes ago
      agentReasoning: "Updated styling for better UX",
    },
    {
      id: "2",
      type: "test_run",
      title: "Tests passed",
      description: "All unit tests successful",
      timestamp: new Date(Date.now() - 1000 * 60 * 15), // 15 minutes ago
    },
    {
      id: "3",
      type: "task_completed",
      title: "Feature complete",
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2), // 2 hours ago
    },
  ];

  it("renders activity feed title", () => {
    render(<ActivityFeed events={[]} />);
    expect(screen.getByText("Activity Feed")).toBeInTheDocument();
  });

  it("shows empty state when no events", () => {
    render(<ActivityFeed events={[]} />);
    expect(screen.getByText("No activity yet")).toBeInTheDocument();
  });

  it("renders all event titles", () => {
    render(<ActivityFeed events={mockEvents} />);
    expect(screen.getByText("File updated")).toBeInTheDocument();
    expect(screen.getByText("Tests passed")).toBeInTheDocument();
    expect(screen.getByText("Feature complete")).toBeInTheDocument();
  });

  it("renders event descriptions when provided", () => {
    render(<ActivityFeed events={mockEvents} />);
    expect(screen.getByText("Modified component.tsx")).toBeInTheDocument();
    expect(screen.getByText("All unit tests successful")).toBeInTheDocument();
  });

  it("renders agent reasoning when provided", () => {
    render(<ActivityFeed events={mockEvents} />);
    expect(screen.getByText(/Updated styling for better UX/)).toBeInTheDocument();
  });

  it("displays event type badges", () => {
    render(<ActivityFeed events={mockEvents} />);
    expect(screen.getByText("file modified")).toBeInTheDocument();
    expect(screen.getByText("test run")).toBeInTheDocument();
    expect(screen.getByText("task completed")).toBeInTheDocument();
  });

  it("formats timestamps correctly for recent events", () => {
    const recentEvent: ActivityEvent = {
      id: "1",
      type: "file_modified",
      title: "Recent change",
      timestamp: new Date(Date.now() - 1000 * 60 * 5), // 5 min ago
    };
    render(<ActivityFeed events={[recentEvent]} />);
    expect(screen.getByText("5m ago")).toBeInTheDocument();
  });

  it("renders icons for each event type", () => {
    const { container } = render(<ActivityFeed events={mockEvents} />);
    const icons = container.querySelectorAll("svg");
    expect(icons.length).toBeGreaterThanOrEqual(mockEvents.length);
  });

  it("applies correct color classes for different event types", () => {
    const { container } = render(<ActivityFeed events={mockEvents} />);
    expect(container.querySelector(".text-blue-500")).toBeInTheDocument();
    expect(container.querySelector(".text-green-500")).toBeInTheDocument();
    expect(container.querySelector(".text-emerald-500")).toBeInTheDocument();
  });

  it("handles error event type", () => {
    const errorEvent: ActivityEvent = {
      id: "1",
      type: "error",
      title: "Error occurred",
      description: "Build failed",
      timestamp: new Date(),
    };
    render(<ActivityFeed events={[errorEvent]} />);
    expect(screen.getByText("Error occurred")).toBeInTheDocument();
    expect(screen.getByText("Build failed")).toBeInTheDocument();
  });

  it("handles approval_requested event type", () => {
    const approvalEvent: ActivityEvent = {
      id: "1",
      type: "approval_requested",
      title: "Approval needed",
      timestamp: new Date(),
    };
    render(<ActivityFeed events={[approvalEvent]} />);
    expect(screen.getByText("Approval needed")).toBeInTheDocument();
  });

  it("applies custom maxHeight", () => {
    const { container } = render(<ActivityFeed events={mockEvents} maxHeight="400px" />);
    const scrollArea = container.querySelector('[style*="max-height"]');
    expect(scrollArea).toHaveStyle({ maxHeight: "400px" });
  });
});
