import { describe, expect, it } from "vitest";
import { sortDeckKeysById } from "./selectors";

describe("sortDeckKeysById", () => {
  it("should_sort_keys_by_id_when_order_is_unspecified", () => {
    const keys = [
      { id: "z-marker", label: "Marqueur" },
      { id: "a-clip", label: "Clip" },
    ];

    expect(sortDeckKeysById(keys)).toEqual([
      { id: "a-clip", label: "Clip" },
      { id: "z-marker", label: "Marqueur" },
    ]);
  });

  it("should_not_mutate_input_when_sorting", () => {
    const keys = [
      { id: "z-marker", label: "Marqueur" },
      { id: "a-clip", label: "Clip" },
    ];
    const original = [...keys];

    sortDeckKeysById(keys);

    expect(keys).toEqual(original);
  });

  it("should_return_empty_when_no_keys", () => {
    expect(sortDeckKeysById([])).toEqual([]);
  });
});
