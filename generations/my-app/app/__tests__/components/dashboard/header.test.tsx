import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { DashboardHeader } from "@/components/dashboard/header";

describe("DashboardHeader", () => {
  const defaultProps = {
    projectName: "Test Project",
    completionPercentage: 75,
    tasksDone: 15,
    tasksTotal: 20,
    filesModified: 42,
    testsPassed: 180,
    testsTotal: 200,
  };

  it("renders project name correctly", () => {
    render(<DashboardHeader {...defaultProps} />);
    expect(screen.getByText("Test Project")).toBeInTheDocument();
  });

  it("displays completion percentage in badge", () => {
    render(<DashboardHeader {...defaultProps} />);
    const badges = screen.getAllByText("75%");
    expect(badges.length).toBeGreaterThan(0);
  });

  it("shows tasks done and total", () => {
    render(<DashboardHeader {...defaultProps} />);
    expect(screen.getByText("15/20")).toBeInTheDocument();
    expect(screen.getByText("Tasks Complete")).toBeInTheDocument();
  });

  it("shows files modified count", () => {
    render(<DashboardHeader {...defaultProps} />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Files Modified")).toBeInTheDocument();
  });

  it("shows tests passed and total", () => {
    render(<DashboardHeader {...defaultProps} />);
    expect(screen.getByText("180/200")).toBeInTheDocument();
    expect(screen.getByText("Tests Passed")).toBeInTheDocument();
  });

  it("renders progress ring with correct percentage", () => {
    render(<DashboardHeader {...defaultProps} />);
    const progressText = screen.getAllByText("75%");
    expect(progressText.length).toBeGreaterThan(0);
  });

  it("handles 0% completion", () => {
    render(<DashboardHeader {...defaultProps} completionPercentage={0} />);
    const badges = screen.getAllByText("0%");
    expect(badges.length).toBeGreaterThan(0);
  });

  it("handles 100% completion", () => {
    render(<DashboardHeader {...defaultProps} completionPercentage={100} />);
    const badges = screen.getAllByText("100%");
    expect(badges.length).toBeGreaterThan(0);
  });

  it("renders all stat icons", () => {
    const { container } = render(<DashboardHeader {...defaultProps} />);
    const icons = container.querySelectorAll("svg");
    expect(icons.length).toBeGreaterThan(3); // At least 3 stat icons plus progress ring
  });

  it("applies responsive grid layout classes", () => {
    const { container } = render(<DashboardHeader {...defaultProps} />);
    const gridElement = container.querySelector(".grid");
    expect(gridElement).toHaveClass("grid-cols-1", "md:grid-cols-3");
  });
});
