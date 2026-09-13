// @vitest-environment jsdom
//
// Collections de scènes (maquette, F-006) — livrées le 2026-09-13. Tests écrits contre le
// composant seul, sans le décor lourd de `ScenesPanel` (rejeu de session, mixeur) : ce que
// ce composant doit prouver n'a rien à voir avec le moteur.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SceneCollections } from "./SceneSkeleton";
import type { SceneLayout } from "./sceneLayout";

afterEach(cleanup);

const EMPTY: SceneLayout = { order: [], labels: {} };

function renderCollections(
  over: Partial<{
    layout: SceneLayout;
    sceneNames: string[];
    activeId: string | null;
  }> = {},
) {
  const onSelectTab = vi.fn();
  const onPersist = vi.fn();
  render(
    <SceneCollections
      layout={over.layout ?? EMPTY}
      sceneNames={over.sceneNames ?? ["main", "jeu"]}
      labelFor={(name) => name}
      activeId={over.activeId ?? null}
      onSelectTab={onSelectTab}
      onPersist={onPersist}
    />,
  );
  return { onSelectTab, onPersist };
}

describe("SceneCollections", () => {
  it("should_show_a_single_button_when_no_collection_exists_yet", () => {
    renderCollections();

    expect(
      screen.getByRole("button", { name: /créer une collection/i }),
    ).toBeTruthy();
    expect(screen.queryByLabelText(/Collections de scènes/)).toBeNull();
  });

  it("should_create_a_collection_from_the_button_and_a_name", () => {
    const { onPersist } = renderCollections();

    fireEvent.click(
      screen.getByRole("button", { name: /créer une collection/i }),
    );
    const input = screen.getByPlaceholderText(/nom de la collection/i);
    fireEvent.change(input, { target: { value: "LoL" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onPersist).toHaveBeenCalledTimes(1);
    const next = onPersist.mock.calls[0][0] as SceneLayout;
    expect(next.collections).toMatchObject([{ name: "LoL", sceneNames: [] }]);
  });

  it("should_show_real_tabs_once_a_collection_exists", () => {
    const layout: SceneLayout = {
      order: [],
      labels: {},
      collections: [{ id: "1", name: "LoL", sceneNames: [] }],
    };
    renderCollections({ layout });

    const tabs = screen.getByLabelText(/Collections de scènes/);
    expect(tabs.getAttribute("aria-disabled")).toBeNull();
    expect(screen.getByText("Toutes")).toBeTruthy();
    expect(screen.getByText("LoL")).toBeTruthy();
  });

  it("should_select_a_tab_on_click", () => {
    const layout: SceneLayout = {
      order: [],
      labels: {},
      collections: [{ id: "1", name: "LoL", sceneNames: [] }],
    };
    const { onSelectTab } = renderCollections({ layout });

    fireEvent.click(screen.getByText("LoL"));

    expect(onSelectTab).toHaveBeenCalledWith("1");
  });

  it("should_rename_a_collection_on_double_click", () => {
    const layout: SceneLayout = {
      order: [],
      labels: {},
      collections: [{ id: "1", name: "LoL", sceneNames: [] }],
    };
    const { onPersist } = renderCollections({ layout });

    fireEvent.doubleClick(screen.getByText("LoL"));
    const input = screen.getByDisplayValue("LoL");
    fireEvent.change(input, { target: { value: "League" } });
    fireEvent.keyDown(input, { key: "Enter" });

    const next = onPersist.mock.calls[0][0] as SceneLayout;
    expect(next.collections).toMatchObject([{ id: "1", name: "League" }]);
  });

  it("should_delete_a_collection_from_the_active_tab_only", () => {
    // Le bouton de suppression n'apparaît que sur l'onglet ACTIF — jamais un « ✕ » sur
    // chaque onglet qui encombrerait la barre pour rien.
    const layout: SceneLayout = {
      order: [],
      labels: {},
      collections: [{ id: "1", name: "LoL", sceneNames: [] }],
    };
    const { onPersist, onSelectTab } = renderCollections({
      layout,
      activeId: "1",
    });

    fireEvent.click(screen.getByTitle(/supprimer cette collection/i));

    const next = onPersist.mock.calls[0][0] as SceneLayout;
    expect(next.collections).toEqual([]);
    expect(onSelectTab).toHaveBeenCalledWith(null);
  });

  it("should_toggle_a_scene_in_and_out_of_the_active_collection", () => {
    const layout: SceneLayout = {
      order: [],
      labels: {},
      collections: [{ id: "1", name: "LoL", sceneNames: ["main"] }],
    };
    const { onPersist } = renderCollections({
      layout,
      activeId: "1",
      sceneNames: ["main", "jeu"],
    });

    fireEvent.click(screen.getByTitle(/choisir les scènes/i));
    const jeuCheckbox = screen.getByLabelText("jeu");
    fireEvent.click(jeuCheckbox);

    const next = onPersist.mock.calls[0][0] as SceneLayout;
    expect(next.collections?.[0].sceneNames).toEqual(["main", "jeu"]);
  });

  it("should_reject_a_name_another_collection_already_uses", () => {
    const layout: SceneLayout = {
      order: [],
      labels: {},
      collections: [{ id: "1", name: "LoL", sceneNames: [] }],
    };
    const { onPersist } = renderCollections({ layout });

    fireEvent.click(screen.getByTitle("Créer une collection"));
    const input = screen.getByPlaceholderText(/nom de la collection/i);
    fireEvent.change(input, { target: { value: "LoL" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onPersist).not.toHaveBeenCalled();
    expect(screen.getByText(/existe déjà/i)).toBeTruthy();
  });
});
