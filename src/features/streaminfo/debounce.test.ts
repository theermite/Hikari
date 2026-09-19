import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { debounce } from "./debounce";

describe("debounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should_call_fn_once_after_the_delay_when_called_once", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 300);

    debounced("a");
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(300);
    expect(fn).toHaveBeenCalledExactlyOnceWith("a");
  });

  it("should_cancel_the_previous_call_when_called_again_before_the_delay", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 300);

    debounced("a");
    vi.advanceTimersByTime(200);
    debounced("b");
    vi.advanceTimersByTime(200);
    // 400ms écoulées au total, mais seulement 200ms depuis le second appel : le premier
    // minuteur devait être annulé, jamais laissé courir en parallèle.
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledExactlyOnceWith("b");
  });

  it("should_not_call_fn_before_the_delay_has_elapsed", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 300);

    debounced();
    vi.advanceTimersByTime(299);
    expect(fn).not.toHaveBeenCalled();
  });
});
