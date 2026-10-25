import { describe, expect, it } from "vitest";
import { blend, formatVolume, orderable, total, type Trough } from "./apothecary";

const troughs: Trough[] = [
  { trough: 1, name: "Red", color: "#ff0000", volume_ul: null },
  { trough: 2, name: "Blue", color: "#0000ff", volume_ul: null },
];

describe("apothecary helpers", () => {
  it("totals a recipe", () => {
    expect(total([{ trough: 1, volume_ul: 40 }, { trough: 2, volume_ul: 10 }])).toBe(50);
  });
  it("blends tints by volume", () => {
    expect(blend([{ trough: 1, volume_ul: 50 }, { trough: 2, volume_ul: 50 }], troughs)).toBe("#800080");
    expect(blend([{ trough: 1, volume_ul: 30 }], troughs)).toBe("#ff0000");
    expect(blend([], troughs)).toBeNull();
  });
  it("keeps only recipes with ingredients, in column order", () => {
    const drafts = {
      3: { column: 3, name: "", ingredients: [{ trough: 1, volume_ul: 10 }] },
      1: { column: 1, name: "", ingredients: [] },
      2: { column: 2, name: "", ingredients: [{ trough: 2, volume_ul: 10 }] },
    };
    expect(orderable(drafts).map((r) => r.column)).toEqual([2, 3]);
  });
  it("formats volumes", () => {
    expect(formatVolume(40)).toBe("40 µL");
    expect(formatVolume(12000)).toBe("12 mL");
    expect(formatVolume(null)).toBe("not set");
  });
});

describe("default concoction names", () => {
  it("follow the plate and column until someone types a name", async () => {
    const { defaultName, withDefaultNames } = await import("./apothecary");
    expect(defaultName("Batch 2", 3)).toBe("Batch 2 column 3");
    const named = withDefaultNames("Batch 2", [
      { column: 1, name: "", ingredients: [{ trough: 1, volume_ul: 10 }] },
      { column: 2, name: "  ", ingredients: [{ trough: 1, volume_ul: 10 }] },
      { column: 3, name: "Kingsfoil tonic", ingredients: [{ trough: 1, volume_ul: 10 }] },
    ]);
    expect(named.map((r) => r.name)).toEqual(["Batch 2 column 1", "Batch 2 column 2", "Kingsfoil tonic"]);
  });
});
