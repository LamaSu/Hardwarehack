// Ready-made orders for demos. Trough numbers refer to the default trough names
// (1 Bruinen Spring Water, 2 Meduseld Mead, 3 Athelas Infusion, 4 Dorwinion Red,
// 5 Light of Eärendil, 6 Ent-draught, 7 Orodruin Ember, 8 Green Dragon Cider,
// 9 Rivendell Rosewater, 10 Mithril Saline, 11 Lembas Broth, 12 Miruvor Cordial).
// Every template stays within the robot's rules: ≥ 5 µL per draw, ≤ 200 µL per well,
// and at most one rack (12 columns) of each tip size.
import type { Recipe } from "./apothecary";

export interface Template { id: string; name: string; recipes: Recipe[] }

const r = (column: number, name: string, ...parts: [number, number][]): Recipe =>
  ({ column, name, ingredients: parts.map(([trough, volume_ul]) => ({ trough, volume_ul })) });

export const TEMPLATES: Template[] = [
  { id: "fellowship", name: "Fellowship sampler", recipes: [
    r(1, "Kingsfoil Tonic", [3, 40], [1, 60]),
    r(2, "Miruvor Restorative", [12, 30], [2, 20], [10, 50]),
    r(3, "Ent-draught Elixir", [6, 80], [8, 20]),
    r(4, "Elven Rosewater Mist", [9, 25], [5, 15], [11, 40]),
  ] },
  { id: "healing", name: "Houses of Healing", recipes: [
    r(1, "Athelas Poultice", [3, 100], [10, 80]),
    r(2, "Kingsfoil Draught", [3, 30], [1, 30], [2, 10]),
    r(3, "Breath of Elbereth", [5, 20], [9, 20], [1, 60]),
  ] },
  { id: "pony", name: "Prancing Pony tasting", recipes: [
    r(1, "Bree Ale Shandy", [8, 50], [2, 50]),
    r(2, "Dorwinion Spritz", [4, 40], [1, 40]),
    r(3, "Ember Toddy", [7, 20], [2, 30], [1, 50]),
    r(4, "Lembas and Honey", [11, 60], [2, 20]),
    r(5, "Ent Cooler", [6, 50], [8, 25]),
    r(6, "Miruvor Nightcap", [12, 25], [5, 15]),
  ] },
];

/**
 * A template's recipes as drafts keyed by column (fresh copies), placed in
 * ``freeColumns`` in order when given (columns that aren't brewed yet).
 */
export function templateDrafts(id: string, freeColumns?: number[]): Record<number, Recipe> {
  const template = TEMPLATES.find((t) => t.id === id);
  if (!template) throw new Error(`Unknown template: ${id}`);
  const columns = freeColumns ?? template.recipes.map((_, i) => i + 1);
  return Object.fromEntries(
    template.recipes.slice(0, columns.length).map((recipe, i) => [columns[i], { ...structuredClone(recipe), column: columns[i] }]),
  );
}
