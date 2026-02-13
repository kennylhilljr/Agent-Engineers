import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { CopilotProvider, useCopilotRuntime } from "@/lib/copilot-provider";

describe("CopilotProvider", () => {
  describe("Component Rendering", () => {
    test("renders children correctly", () => {
      render(
        <CopilotProvider>
          <div data-testid="child-element">Test Child</div>
        </CopilotProvider>
      );

      expect(screen.getByTestId("child-element")).toBeInTheDocument();
      expect(screen.getByText("Test Child")).toBeInTheDocument();
    });

    test("applies copilot provider data attribute", () => {
      const { container } = render(
        <CopilotProvider>
          <div>Test</div>
        </CopilotProvider>
      );

      const provider = container.querySelector('[data-copilot-provider="true"]');
      expect(provider).toBeInTheDocument();
    });

    test("sets runtime URL data attribute", () => {
      const { container } = render(
        <CopilotProvider>
          <div>Test</div>
        </CopilotProvider>
      );

      const provider = container.querySelector('[data-runtime-url="/api/ag-ui"]');
      expect(provider).toBeInTheDocument();
    });
  });

  describe("Multiple Children", () => {
    test("renders multiple children", () => {
      render(
        <CopilotProvider>
          <div data-testid="child-1">Child 1</div>
          <div data-testid="child-2">Child 2</div>
          <div data-testid="child-3">Child 3</div>
        </CopilotProvider>
      );

      expect(screen.getByTestId("child-1")).toBeInTheDocument();
      expect(screen.getByTestId("child-2")).toBeInTheDocument();
      expect(screen.getByTestId("child-3")).toBeInTheDocument();
    });

    test("renders nested component trees", () => {
      render(
        <CopilotProvider>
          <div data-testid="parent">
            <div data-testid="child">
              <span data-testid="grandchild">Nested</span>
            </div>
          </div>
        </CopilotProvider>
      );

      expect(screen.getByTestId("parent")).toBeInTheDocument();
      expect(screen.getByTestId("child")).toBeInTheDocument();
      expect(screen.getByTestId("grandchild")).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    test("handles null children gracefully", () => {
      render(
        <CopilotProvider>
          {null}
        </CopilotProvider>
      );

      // Should not crash
      const provider = document.querySelector('[data-copilot-provider="true"]');
      expect(provider).toBeInTheDocument();
    });

    test("handles undefined children gracefully", () => {
      render(
        <CopilotProvider>
          {undefined}
        </CopilotProvider>
      );

      // Should not crash
      const provider = document.querySelector('[data-copilot-provider="true"]');
      expect(provider).toBeInTheDocument();
    });

    test("handles fragments as children", () => {
      render(
        <CopilotProvider>
          <>
            <div data-testid="fragment-child-1">Fragment 1</div>
            <div data-testid="fragment-child-2">Fragment 2</div>
          </>
        </CopilotProvider>
      );

      expect(screen.getByTestId("fragment-child-1")).toBeInTheDocument();
      expect(screen.getByTestId("fragment-child-2")).toBeInTheDocument();
    });
  });
});

describe("useCopilotRuntime", () => {
  const TestComponent = () => {
    const runtime = useCopilotRuntime();
    return (
      <div>
        <div data-testid="connected-status">
          {runtime.isConnected ? "connected" : "disconnected"}
        </div>
        <button
          data-testid="send-button"
          onClick={() => runtime.sendMessage("test")}
        >
          Send
        </button>
      </div>
    );
  };

  test("returns runtime object with isConnected property", () => {
    render(
      <CopilotProvider>
        <TestComponent />
      </CopilotProvider>
    );

    expect(screen.getByTestId("connected-status")).toHaveTextContent(
      "disconnected"
    );
  });

  test("returns runtime object with sendMessage function", () => {
    const consoleSpy = jest.spyOn(console, "log").mockImplementation();

    render(
      <CopilotProvider>
        <TestComponent />
      </CopilotProvider>
    );

    const button = screen.getByTestId("send-button");
    button.click();

    expect(consoleSpy).toHaveBeenCalledWith(
      "CopilotKit sendMessage:",
      "test"
    );

    consoleSpy.mockRestore();
  });

  test("sendMessage is async", async () => {
    const runtime = useCopilotRuntime();
    const result = runtime.sendMessage("test");

    expect(result).toBeInstanceOf(Promise);
    await result;
  });
});
