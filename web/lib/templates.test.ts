import { describe, expect, it } from "vitest";
import { MIN_DRAW_UL, total, WELL_CAPACITY_UL } from "./apothecary";
import { DEFAULT_TEMPLATE_ID, TEMPLATES, templateDrafts } from "./templates";

describe("order templates", () => {
  it("default to the Prancing Pony tasting", () => {
    expect(TEMPLATES.find((t) => t.id === DEFAULT_TEMPLATE_ID)?.name).toBe("Prancing Pony tasting");
  });

  it("have unique ids and names", () => {
    expect(new Set(TEMPLATES.map((t) => t.id)).size).toBe(TEMPLATES.length);
    expect(TEMPLATES.length).toBeGreaterThanOrEqual(3);
  });

  it.each(TEMPLATES.map((t) => [t.name, t]))("%s respects the robot's rules", (_, template) => {
    const columns = template.recipes.map((r) => r.column);
    expect(new Set(columns).size).toBe(columns.length);
    for (const r of template.recipes) {
      expect(r.name.length).toBeGreaterThan(0);
      expect(total(r.ingredients)).toBeLessThanOrEqual(WELL_CAPACITY_UL);
      for (const i of r.ingredients) {
        expect(i.volume_ul).toBeGreaterThanOrEqual(MIN_DRAW_UL);
        expect(i.trough).toBeGreaterThanOrEqual(1);
        expect(i.trough).toBeLessThanOrEqual(12);
      }
    }
    const draws = template.recipes.flatMap((r) => r.ingredients);
    expect(draws.filter((i) => i.volume_ul <= 50).length).toBeLessThanOrEqual(12); // one rack of 50 µL tips
    expect(draws.filter((i) => i.volume_ul > 50).length).toBeLessThanOrEqual(12);  // one rack of 1000 µL tips
  });

  it("fills columns 1.. by default and the free columns when given", () => {
    const first = TEMPLATES[0];
    expect(Object.keys(templateDrafts(first.id)).map(Number)).toEqual(first.recipes.map((_, i) => i + 1));
    const placed = templateDrafts(first.id, [2, 5, 6, 9]);
    expect(Object.keys(placed).map(Number)).toEqual([2, 5, 6, 9]);
    expect(placed[5].name).toBe(first.recipes[1].name);
    expect(Object.keys(templateDrafts(first.id, [11, 12])).map(Number)).toEqual([11, 12]);
  });

  it("returns fresh copies", () => {
    const a = templateDrafts(TEMPLATES[0].id);
    a[1].ingredients[0].volume_ul = 999;
    expect(templateDrafts(TEMPLATES[0].id)[1].ingredients[0].volume_ul).not.toBe(999);
  });

  it("refuses an unknown template", () => {
    expect(() => templateDrafts("nope")).toThrow();
  });
});
