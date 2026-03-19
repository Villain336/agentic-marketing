import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ToggleRow } from "@/components/ui/toggle-row";
import { EventDot } from "@/components/ui/event-dot";
import { ContextBlock } from "@/components/ui/context-block";
import { STATUS_COLORS, GRADE_COLORS } from "@/components/ui/status-dot";

describe("ToggleRow", () => {
  it("renders label and description", () => {
    render(
      <ToggleRow
        label="Test Label"
        description="Test description"
        checked={false}
        onChange={() => {}}
      />
    );
    expect(screen.getByText("Test Label")).toBeInTheDocument();
    expect(screen.getByText("Test description")).toBeInTheDocument();
  });

  it("calls onChange when clicked", () => {
    const onChange = jest.fn();
    render(
      <ToggleRow
        label="Toggle"
        description="Desc"
        checked={false}
        onChange={onChange}
      />
    );
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("toggles off when checked", () => {
    const onChange = jest.fn();
    render(
      <ToggleRow
        label="Toggle"
        description="Desc"
        checked={true}
        onChange={onChange}
      />
    );
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith(false);
  });
});

describe("EventDot", () => {
  it("renders with correct color for completed events", () => {
    const { container } = render(<EventDot type="agent.completed" />);
    expect(container.firstChild).toHaveClass("bg-emerald-500");
  });

  it("renders with correct color for error events", () => {
    const { container } = render(<EventDot type="agent.failed" />);
    expect(container.firstChild).toHaveClass("bg-red-500");
  });

  it("renders with correct color for started events", () => {
    const { container } = render(<EventDot type="agent.started" />);
    expect(container.firstChild).toHaveClass("bg-blue-500");
  });

  it("renders with default color for unknown events", () => {
    const { container } = render(<EventDot type="unknown.event" />);
    expect(container.firstChild).toHaveClass("bg-surface-300");
  });
});

describe("ContextBlock", () => {
  it("renders label and value", () => {
    render(<ContextBlock label="Business" value="TestCo" />);
    expect(screen.getByText("Business")).toBeInTheDocument();
    expect(screen.getByText("TestCo")).toBeInTheDocument();
  });

  it("returns null when value is undefined", () => {
    const { container } = render(<ContextBlock label="Business" />);
    expect(container.firstChild).toBeNull();
  });

  it("returns null when value is empty string", () => {
    const { container } = render(<ContextBlock label="Business" value="" />);
    // Empty string is falsy, so it returns null
    expect(container.firstChild).toBeNull();
  });
});

describe("STATUS_COLORS", () => {
  it("has colors for all agent statuses", () => {
    expect(STATUS_COLORS.idle).toBeDefined();
    expect(STATUS_COLORS.queued).toBeDefined();
    expect(STATUS_COLORS.running).toBeDefined();
    expect(STATUS_COLORS.done).toBeDefined();
    expect(STATUS_COLORS.error).toBeDefined();
  });
});

describe("GRADE_COLORS", () => {
  it("has colors for all grades", () => {
    const grades = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "D-", "F", "—"];
    for (const grade of grades) {
      expect(GRADE_COLORS[grade]).toBeDefined();
    }
  });
});
