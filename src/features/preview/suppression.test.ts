import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  isPreviewSuppressed,
  onPreviewSuppressionChange,
  resetPreviewSuppression,
  suppressPreview,
} from "./suppression";

describe("suppressPreview", () => {
  beforeEach(() => {
    resetPreviewSuppression();
  });

  it("should_not_suppress_the_preview_when_nobody_asked", () => {
    expect(isPreviewSuppressed()).toBe(false);
  });

  it("should_suppress_the_preview_while_one_holder_asks", () => {
    suppressPreview();

    expect(isPreviewSuppressed()).toBe(true);
  });

  it("should_show_the_preview_again_once_the_only_holder_releases", () => {
    const release = suppressPreview();

    release();

    expect(isPreviewSuppressed()).toBe(false);
  });

  it("should_keep_the_preview_hidden_while_another_holder_still_asks", () => {
    // Deux fenêtres ouvertes en même temps : la première qui se ferme ne doit pas
    // réafficher l'aperçu par-dessus la seconde.
    const first = suppressPreview();
    suppressPreview();

    first();

    expect(isPreviewSuppressed()).toBe(true);
  });

  it("should_count_a_double_release_only_once", () => {
    // Un démontage React en double réafficherait sinon l'aperçu sous une fenêtre ouverte.
    const first = suppressPreview();
    suppressPreview();

    first();
    first();

    expect(isPreviewSuppressed()).toBe(true);
  });

  it("should_never_let_the_count_go_negative", () => {
    const release = suppressPreview();
    release();

    suppressPreview();

    expect(isPreviewSuppressed()).toBe(true);
  });

  it("should_tell_subscribers_when_the_state_changes", () => {
    const listener = vi.fn();
    onPreviewSuppressionChange(listener);

    const release = suppressPreview();
    release();

    expect(listener).toHaveBeenNthCalledWith(1, true);
    expect(listener).toHaveBeenNthCalledWith(2, false);
  });

  it("should_stop_telling_a_subscriber_that_unsubscribed", () => {
    const listener = vi.fn();
    const unsubscribe = onPreviewSuppressionChange(listener);

    unsubscribe();
    suppressPreview();

    expect(listener).not.toHaveBeenCalled();
  });
});
