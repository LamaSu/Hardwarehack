// Well naming, matching drug-screen-platform/src/plate_formats.py.

export function rowLabel(rowIndex: number): string {
  let label = "";
  let index = rowIndex + 1;
  while (index > 0) {
    const remainder = (index - 1) % 26;
    index = Math.floor((index - 1) / 26);
    label = String.fromCharCode(65 + remainder) + label;
  }
  return label;
}

export function wellName(row: number, column: number): string {
  return `${rowLabel(row)}${column + 1}`;
}

export function parseWell(name: string): [number, number] {
  const match = /^([A-Z]+)(\d+)$/.exec(name);
  if (!match) throw new Error(`Invalid well name: ${name}`);
  let row = 0;
  for (const ch of match[1]) row = row * 26 + (ch.charCodeAt(0) - 64);
  return [row - 1, Number(match[2]) - 1];
}

export function wellSortKey(name: string): [number, number] {
  return parseWell(name);
}

export function compareWells(a: string, b: string): number {
  const [ra, ca] = parseWell(a);
  const [rb, cb] = parseWell(b);
  return ra - rb || ca - cb;
}

/** Wells in the rectangle spanned by two wells (inclusive). */
export function wellsInRect(a: string, b: string): string[] {
  const [r1, c1] = parseWell(a);
  const [r2, c2] = parseWell(b);
  const wells: string[] = [];
  for (let r = Math.min(r1, r2); r <= Math.max(r1, r2); r++)
    for (let c = Math.min(c1, c2); c <= Math.max(c1, c2); c++) wells.push(wellName(r, c));
  return wells;
}
