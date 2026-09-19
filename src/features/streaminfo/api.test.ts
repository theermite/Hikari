import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import { getStreamInfo, searchCategories, updateStreamInfo } from "./api";

describe("streaminfo api", () => {
  beforeEach(() => {
    vi.mocked(invoke).mockReset();
  });

  it("should_call_stream_info_get_command_when_reading_channel_info", async () => {
    vi.mocked(invoke).mockResolvedValueOnce({
      title: "x",
      game_id: "1",
      game_name: "y",
      tags: [],
    });

    await getStreamInfo();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("stream_info_get");
  });

  it("should_call_stream_info_search_categories_command_with_the_query", async () => {
    vi.mocked(invoke).mockResolvedValueOnce([]);

    await searchCategories("fortnite");

    expect(invoke).toHaveBeenCalledExactlyOnceWith(
      "stream_info_search_categories",
      {
        query: "fortnite",
      },
    );
  });

  it("should_call_stream_info_update_command_with_the_patch", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await updateStreamInfo({ title: "Nouveau titre" });

    expect(invoke).toHaveBeenCalledExactlyOnceWith("stream_info_update", {
      patch: { title: "Nouveau titre" },
    });
  });
});
