import { describe, expect, it } from "vitest";

import {
  CHAT_HISTORY_CAP,
  filterChatMessages,
  pushChatMessage,
} from "./history";
import type { ChatMessage, DisplayedChatMessage } from "./types";

function message(
  platform: ChatMessage["platform"],
  username: string,
  text: string,
): ChatMessage {
  return { platform, username, text };
}

describe("chat history", () => {
  it("should_merge_multiplatform_chat", () => {
    let history: DisplayedChatMessage[] = [];
    history = pushChatMessage(history, message("twitch", "Ange", "coucou"), 1);
    history = pushChatMessage(history, message("youtube", "Jay", "hello"), 2);

    expect(history).toEqual([
      { platform: "twitch", username: "Ange", text: "coucou", id: 1 },
      { platform: "youtube", username: "Jay", text: "hello", id: 2 },
    ]);
  });

  it("should_cap_chat_history_at_the_limit", () => {
    let history: DisplayedChatMessage[] = [];
    for (let i = 0; i < CHAT_HISTORY_CAP + 5; i++) {
      history = pushChatMessage(history, message("twitch", "x", String(i)), i);
    }

    expect(history).toHaveLength(CHAT_HISTORY_CAP);
    // Les plus ANCIENS sont retirés — le message le plus récent reste visible.
    expect(history[0].text).toBe("5");
    expect(history[history.length - 1].text).toBe(String(CHAT_HISTORY_CAP + 4));
  });

  it("should_filter_by_platform", () => {
    let history: DisplayedChatMessage[] = [];
    history = pushChatMessage(history, message("twitch", "Ange", "a"), 1);
    history = pushChatMessage(history, message("youtube", "Jay", "b"), 2);

    expect(filterChatMessages(history, "twitch")).toEqual([
      { platform: "twitch", username: "Ange", text: "a", id: 1 },
    ]);
    expect(filterChatMessages(history, "youtube")).toEqual([
      { platform: "youtube", username: "Jay", text: "b", id: 2 },
    ]);
  });

  it("should_show_both_platforms_when_filter_is_both", () => {
    let history: DisplayedChatMessage[] = [];
    history = pushChatMessage(history, message("twitch", "Ange", "a"), 1);
    history = pushChatMessage(history, message("youtube", "Jay", "b"), 2);

    expect(filterChatMessages(history, "both")).toHaveLength(2);
  });
});
