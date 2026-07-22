// A loose mirror of the engine's wire protocol (`hikari-protocol::EngineMessage`) — only
// the fields this status screen actually reads (F-003 spirit: never invent a shape the
// wire hasn't sent). Not a full protocol port; extend when a screen needs another field.

export interface EngineMessage {
  type: string;
  message?: string;
  items?: Array<{ name: string; kind: string }>;
}
