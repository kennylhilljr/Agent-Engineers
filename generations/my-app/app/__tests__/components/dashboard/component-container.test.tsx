import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ComponentContainer } from "@/components/dashboard/component-container";

describe("ComponentContainer", () => {
  it("shows empty state when no components", () => {
    render(<ComponentContainer />);
    expect(screen.getByText("Ready for AI Generation")).toBeInTheDocument();
    expect(
      screen.getByText(/Waiting for agent to generate components/)
    ).toBeInTheDocument();
  });

  it("shows loading state", () => {
    render(<ComponentContainer isLoading={true} />);
    expect(screen.getByText("Agent is generating components...")).toBeInTheDocument();
  });

  it("shows error state with error message", () => {
    const errorMessage = "Failed to load components";
    render(<ComponentContainer error={errorMessage} />);
    expect(screen.getByText("Error Loading Components")).toBeInTheDocument();
    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it("renders components in grid layout", () => {
    const mockComponents = [
      <div key="1">Component 1</div>,
      <div key="2">Component 2</div>,
      <div key="3">Component 3</div>,
    ];
    const { container } = render(<ComponentContainer components={mockComponents} />);
    expect(screen.getByText("Component 1")).toBeInTheDocument();
    expect(screen.getByText("Component 2")).toBeInTheDocument();
    expect(screen.getByText("Component 3")).toBeInTheDocument();

    const grid = container.querySelector(".grid");
    expect(grid).toHaveClass("grid-cols-1", "md:grid-cols-2", "lg:grid-cols-3");
  });

  it("applies responsive grid classes", () => {
    const mockComponents = [<div key="1">Test</div>];
    const { container } = render(<ComponentContainer components={mockComponents} />);
    const grid = container.querySelector(".grid");
    expect(grid).toHaveClass("grid-cols-1");
    expect(grid).toHaveClass("md:grid-cols-2");
    expect(grid).toHaveClass("lg:grid-cols-3");
  });

  it("shows loading spinner in loading state", () => {
    const { container } = render(<ComponentContainer isLoading={true} />);
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("prioritizes error state over loading state", () => {
    render(<ComponentContainer isLoading={true} error="Error occurred" />);
    expect(screen.getByText("Error Loading Components")).toBeInTheDocument();
    expect(screen.queryByText("Agent is generating components...")).not.toBeInTheDocument();
  });

  it("prioritizes error state over empty state", () => {
    render(<ComponentContainer components={[]} error="Error occurred" />);
    expect(screen.getByText("Error Loading Components")).toBeInTheDocument();
    expect(screen.queryByText("Ready for AI Generation")).not.toBeInTheDocument();
  });

  it("shows components instead of empty state when components exist", () => {
    const mockComponents = [<div key="1">Component</div>];
    render(<ComponentContainer components={mockComponents} />);
    expect(screen.getByText("Component")).toBeInTheDocument();
    expect(screen.queryByText("Ready for AI Generation")).not.toBeInTheDocument();
  });

  it("renders empty state icon", () => {
    const { container } = render(<ComponentContainer />);
    const icon = container.querySelector("svg");
    expect(icon).toBeInTheDocument();
  });

  it("renders error state icon", () => {
    const { container } = render(<ComponentContainer error="Error" />);
    const icons = container.querySelectorAll("svg");
    expect(icons.length).toBeGreaterThan(0);
  });
});
