import { beforeEach, describe, expect, it, vi } from "vitest";

// Même contrainte que `camera/api.test.ts` : aucun runtime Tauri sous vitest — `invoke`
// est simulé pour ne tester que le CÂBLAGE (nom de commande, forme de la réponse).
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import {
  banChatUser,
  connectChat,
  disconnectChat,
  sendChatMessage,
  timeoutChatUser,
} from "./api";

describe("chat api", () => {
  beforeEach(() => {
    vi.mocked(invoke).mockReset();
  });

  it("should_call_chat_connect_command_when_connecting", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await connectChat();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("chat_connect");
  });

  it("should_call_chat_send_command_with_the_text_when_sending", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await sendChatMessage("gg bien joué");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("chat_send", {
      text: "gg bien joué",
    });
  });

  it("should_call_chat_disconnect_command_when_disconnecting", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await disconnectChat();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("chat_disconnect");
  });

  it("should_call_chat_timeout_user_command_with_user_and_duration_when_muting", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await timeoutChatUser("141981764", 600);

    expect(invoke).toHaveBeenCalledExactlyOnceWith("chat_timeout_user", {
      userId: "141981764",
      durationSecs: 600,
    });
  });

  it("should_call_chat_ban_user_command_with_the_targeted_user_when_banning", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await banChatUser("141981764");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("chat_ban_user", {
      userId: "141981764",
    });
  });
});
