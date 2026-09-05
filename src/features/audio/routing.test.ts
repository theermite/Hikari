// Le routage audio traduit UN réglage moteur à trois valeurs en DEUX cases à cocher.
// Ce filet garde la traduction dans les deux sens, et surtout le contre-sens qui coûterait
// le plus cher : croire que `none` veut dire « aucune sortie ».

import { describe, expect, it } from "vitest";
import {
  type AudioRouting,
  toMonitoring,
  toRouting,
  wouldSilenceEverything,
} from "./routing";

describe("toRouting", () => {
  it("should_read_none_as_broadcast_only_never_as_silence", () => {
    // Dans libobs, `none` signifie « pas de retour casque » — le son continue d'aller au
    // direct. Le lire comme « aucune sortie » ferait croire à l'utilisateur qu'il a coupé
    // une piste que son public entend toujours.
    expect(toRouting("none")).toEqual({ listen: false, broadcast: true });
  });

  it("should_read_monitor_only_as_headphones_without_the_audience", () => {
    expect(toRouting("monitor_only")).toEqual({
      listen: true,
      broadcast: false,
    });
  });

  it("should_read_monitor_and_output_as_both", () => {
    expect(toRouting("monitor_and_output")).toEqual({
      listen: true,
      broadcast: true,
    });
  });
});

describe("toMonitoring", () => {
  it("should_map_each_visible_combination_back_to_the_engine", () => {
    expect(toMonitoring({ listen: false, broadcast: true })).toBe("none");
    expect(toMonitoring({ listen: true, broadcast: false })).toBe(
      "monitor_only",
    );
    expect(toMonitoring({ listen: true, broadcast: true })).toBe(
      "monitor_and_output",
    );
  });

  it("should_keep_broadcasting_when_asked_for_an_impossible_state", () => {
    // libobs n'a pas d'état « ni l'un ni l'autre ». Garder la diffusion est le seul choix
    // qui ne fasse pas disparaître le son sans l'annoncer — couper, c'est le rôle du
    // bouton « Couper », qui le dit.
    expect(toMonitoring({ listen: false, broadcast: false })).toBe("none");
  });
});

describe("toRouting et toMonitoring", () => {
  it("should_round_trip_every_engine_value", () => {
    for (const value of [
      "none",
      "monitor_only",
      "monitor_and_output",
    ] as const) {
      expect(toMonitoring(toRouting(value))).toBe(value);
    }
  });
});

describe("wouldSilenceEverything", () => {
  const both: AudioRouting = { listen: true, broadcast: true };

  it("should_allow_unchecking_one_when_the_other_remains", () => {
    expect(wouldSilenceEverything(both, "listen")).toBe(false);
    expect(wouldSilenceEverything(both, "broadcast")).toBe(false);
  });

  it("should_refuse_unchecking_the_last_remaining_destination", () => {
    expect(
      wouldSilenceEverything({ listen: false, broadcast: true }, "broadcast"),
    ).toBe(true);
    expect(
      wouldSilenceEverything({ listen: true, broadcast: false }, "listen"),
    ).toBe(true);
  });

  it("should_never_block_checking_a_box", () => {
    // Cocher ajoute une destination : ça ne peut jamais rendre la piste muette.
    expect(
      wouldSilenceEverything({ listen: false, broadcast: true }, "listen"),
    ).toBe(false);
  });
});
