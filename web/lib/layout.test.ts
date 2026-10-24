import { describe, expect, it } from "vitest";
import { applyDoseSeries, assign, changeFormat, concentrationRangeNm, drugs, emptyLayout, wellsOutside } from "./layout";
import { parseWell, rowLabel, wellName, wellsInRect } from "./wells";

// Same plate as planning.example_layout() in Python; expected values come from it.
function exampleLayout() {
  let layout = emptyLayout("96-well", "Example screen");
  const block = (rows: number[], cols: number[]) => rows.flatMap((r) => cols.map((c) => wellName(r, c)));
  const cols = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  layout = applyDoseSeries(layout, block([0, 1, 2], cols), "Erastin", 20, "µM", 2);
  layout = applyDoseSeries(layout, block([3, 4, 5], cols), "RSL3", 1, "µM", 3);
  layout = assign(layout, block([0, 1, 2, 3, 4, 5], [0]), { role: "Vehicle control", drug: "DMSO", concentration: null, unit: "µM" });
  layout = assign(layout, block([0, 1, 2, 3, 4, 5], [11]), { role: "Positive control", drug: "Staurosporine", concentration: 1, unit: "µM" });
  return layout;
}

describe("wells", () => {
  it("names rows like the Python code", () => {
    expect(rowLabel(0)).toBe("A");
    expect(rowLabel(25)).toBe("Z");
    expect(wellName(26, 0)).toBe("AA1");
    expect(parseWell("AF48")).toEqual([31, 47]);
  });
  it("selects rectangles in either direction", () => {
    expect(wellsInRect("B2", "A1")).toEqual(["A1", "A2", "B1", "B2"]);
  });
});

describe("layout", () => {
  it("dose series matches Python", () => {
    const w = exampleLayout().wells;
    expect(w.A2.concentration).toBe(20);
    expect(w.A3.concentration).toBe(10);
    expect(w.A11.concentration).toBe(0.03906);
    expect(w.D2.concentration).toBe(1);
    expect(w.D11.concentration).toBe(5.081e-5);
  });
  it("down-column series", () => {
    const l = applyDoseSeries(emptyLayout(), ["A1", "B1", "C1"], "X", 9, "µM", 3, "column");
    expect([l.wells.A1.concentration, l.wells.B1.concentration, l.wells.C1.concentration]).toEqual([9, 3, 1]);
  });
  it("drugs in row-wise order and ranges", () => {
    const l = exampleLayout();
    expect(drugs(l)).toEqual(["DMSO", "Erastin", "Staurosporine", "RSL3"]);
    expect(concentrationRangeNm(l, "RSL3")).toEqual([0.05081, 1000]);
  });
  it("format change drops outside wells", () => {
    const l = exampleLayout();
    expect(wellsOutside(l, 2, 3).length).toBeGreaterThan(0);
    const small = changeFormat(l, { name: "6-well", rows: 2, columns: 3, max_volume_ul: 0, default_working_volume_ul: 0, opentrons_load_name: null, well_count: 6, flex_note: null });
    expect(Object.keys(small.wells).sort()).toEqual(["A1", "A2", "A3", "B1", "B2", "B3"]);
  });
  it("rejects a factor of 1", () => {
    expect(() => applyDoseSeries(emptyLayout(), ["A1"], "X", 1, "µM", 1)).toThrow();
  });
});
