import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import DashboardPage from "@/app/(dashboard)/[projectId]/page";

describe("DashboardPage", () => {
  const mockParams = Promise.resolve({ projectId: "test-project-123" });

  it("renders dashboard header", async () => {
    render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      expect(screen.getByText("AI Coding Dashboard")).toBeInTheDocument();
    });
  });

  it("displays project statistics", async () => {
    render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      expect(screen.getByText("Tasks Complete")).toBeInTheDocument();
      expect(screen.getByText("Files Modified")).toBeInTheDocument();
      expect(screen.getByText("Tests Passed")).toBeInTheDocument();
    });
  });

  it("renders activity feed", async () => {
    render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      expect(screen.getByText("Activity Feed")).toBeInTheDocument();
    });
  });

  it("shows initial activity events", async () => {
    render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      expect(screen.getByText("Database schema created")).toBeInTheDocument();
      expect(screen.getByText("Unit tests passed")).toBeInTheDocument();
    });
  });

  it("renders agent chat placeholder", async () => {
    render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      expect(screen.getByText("Agent Chat")).toBeInTheDocument();
      expect(
        screen.getByText(/CopilotKit chat interface will be integrated here/)
      ).toBeInTheDocument();
    });
  });

  it("renders component container", async () => {
    render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      expect(screen.getByText("Ready for AI Generation")).toBeInTheDocument();
    });
  });

  it("uses responsive grid layout", async () => {
    const { container } = render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      const grids = container.querySelectorAll(".grid");
      expect(grids.length).toBeGreaterThan(0);
      const mainGrid = Array.from(grids).find((grid) =>
        grid.classList.contains("lg:grid-cols-3")
      );
      expect(mainGrid).toBeInTheDocument();
    });
  });

  it("displays completion percentage", async () => {
    render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      const percentages = screen.getAllByText("35%");
      expect(percentages.length).toBeGreaterThan(0);
    });
  });

  it("shows task progress", async () => {
    render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      expect(screen.getByText("7/20")).toBeInTheDocument();
    });
  });

  it("displays test results", async () => {
    render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      expect(screen.getByText("156/200")).toBeInTheDocument();
    });
  });

  it("shows files modified count", async () => {
    render(<DashboardPage params={mockParams} />);
    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument();
    });
  });
});
