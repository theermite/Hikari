import type { DockviewApi, SerializedDockview } from "dockview-react";
import { describe, expect, it, vi } from "vitest";
import { restoreLayout } from "./layout";

// `saveLayout`/`loadLayout` touch the real Tauri plugin-store (IPC) — no Tauri runtime
// exists under vitest (same constraint as every OS-touching module this project has:
// libobs, the local OAuth listeners). Only `restoreLayout`'s pure wiring is testable here.
describe("restoreLayout", () => {
  it("should_restore_layout_when_deserialized", () => {
    const layout = {
      grid: { root: {}, width: 0, height: 0 },
    } as unknown as SerializedDockview;
    const fromJSON = vi.fn();
    const fakeApi = { fromJSON } as unknown as DockviewApi;

    restoreLayout(fakeApi, layout);

    expect(fromJSON).toHaveBeenCalledExactlyOnceWith(layout);
  });
});
