"use client";
// Interactive SVG plate: click, drag a rectangle, click/drag row or column labels,
// corner = select all. Shift or Ctrl/Cmd adds to the selection; Ctrl/Cmd-click toggles a well.
import { useEffect, useRef } from "react";
import { wellStyle } from "@/lib/colors";
import type { Layout, PlateFormat } from "@/lib/layout";
import { rowLabel, wellName, wellsInRect } from "@/lib/wells";

interface Props {
  layout: Layout;
  format: PlateFormat;
  selection: Set<string>;
  onSelect: (selection: Set<string>) => void;
  onHover: (well: string | null) => void;
}

interface Drag { anchor: string; base: Set<string>; toggle: boolean; moved: boolean }

export default function PlateMap({ layout, format, selection, onSelect, onHover }: Props) {
  const drag = useRef<Drag | null>(null);
  // Row/column label drags: index of the label where the drag started.
  const rowDrag = useRef<number | null>(null);
  const colDrag = useRef<number | null>(null);
  const { rows, columns } = format;
  const pitch = Math.max(14, Math.min(64, Math.floor(900 / columns), Math.floor(560 / rows)));
  const radius = pitch * 0.42;
  const gutter = Math.max(22, pitch * 0.6);
  const width = gutter + columns * pitch + 4;
  const height = gutter + rows * pitch + 4;
  const labelSize = Math.max(8, Math.min(13, pitch * 0.3));
  const lastCol = columns - 1;
  const lastRow = rows - 1;

  useEffect(() => {
    const end = () => {
      const d = drag.current;
      if (d && !d.moved && d.toggle) {
        const next = new Set(d.base);
        if (next.has(d.anchor)) next.delete(d.anchor); else next.add(d.anchor);
        onSelect(next);
      }
      drag.current = null;
      rowDrag.current = null;
      colDrag.current = null;
    };
    window.addEventListener("pointerup", end);
    return () => window.removeEventListener("pointerup", end);
  }, [onSelect]);

  const start = (anchor: string, end: string, event: React.PointerEvent) => {
    event.preventDefault();
    const additive = event.shiftKey || event.ctrlKey || event.metaKey;
    const base = additive ? new Set(selection) : new Set<string>();
    drag.current = { anchor, base, toggle: (event.ctrlKey || event.metaKey) && anchor === end, moved: false };
    if (!drag.current.toggle) onSelect(new Set([...base, ...wellsInRect(anchor, end)]));
  };
  const extend = (end: string) => {
    const d = drag.current;
    if (!d) return;
    d.moved = d.moved || end !== d.anchor;
    onSelect(new Set([...d.base, ...wellsInRect(d.anchor, end)]));
  };

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="select-none touch-none"
      onPointerLeave={() => onHover(null)}
      role="grid"
      aria-label={`${format.name} plate`}
    >
      <rect
        x={0} y={0} width={gutter - 2} height={gutter - 2} rx={3}
        className="cursor-pointer fill-field hover:fill-line"
        onPointerDown={(e) => { e.preventDefault(); onSelect(new Set(Array.from({ length: rows * columns }, (_, i) => wellName(Math.floor(i / columns), i % columns)))); }}
      >
        <title>Select all</title>
      </rect>
      {Array.from({ length: columns }, (_, c) => (
        <text
          key={`c${c}`} x={gutter + c * pitch + pitch / 2} y={gutter / 2 + labelSize / 3}
          textAnchor="middle" fontSize={labelSize} className="cursor-pointer fill-muted hover:fill-text"
          onPointerDown={(e) => { colDrag.current = c; start(wellName(0, c), wellName(lastRow, c), e); drag.current!.toggle = false; }}
          onPointerEnter={() => { if (colDrag.current !== null) { drag.current!.anchor = wellName(0, colDrag.current); extend(wellName(lastRow, c)); } }}
        >
          {columns > 24 && c % 2 === 1 ? "" : c + 1}
        </text>
      ))}
      {Array.from({ length: rows }, (_, r) => (
        <text
          key={`r${r}`} x={gutter / 2} y={gutter + r * pitch + pitch / 2 + labelSize / 3}
          textAnchor="middle" fontSize={labelSize} className="cursor-pointer fill-muted hover:fill-text"
          onPointerDown={(e) => { rowDrag.current = r; start(wellName(r, 0), wellName(r, lastCol), e); drag.current!.toggle = false; }}
          onPointerEnter={() => { if (rowDrag.current !== null) { drag.current!.anchor = wellName(rowDrag.current, 0); extend(wellName(r, lastCol)); } }}
        >
          {rowLabel(r)}
        </text>
      ))}
      {Array.from({ length: rows * columns }, (_, i) => {
        const r = Math.floor(i / columns);
        const c = i % columns;
        const well = wellName(r, c);
        const style = wellStyle(layout, layout.wells[well]);
        const selected = selection.has(well);
        const cx = gutter + c * pitch + pitch / 2;
        const cy = gutter + r * pitch + pitch / 2;
        return (
          <g
            key={well}
            className="cursor-pointer"
            onPointerDown={(e) => start(well, well, e)}
            onPointerEnter={() => { onHover(well); if (rowDrag.current === null && colDrag.current === null) extend(well); }}
          >
            <circle cx={cx} cy={cy} r={radius} fill={style.ring ? style.ring : style.fill} />
            {style.ring && <circle cx={cx} cy={cy} r={radius * 0.45} fill={style.fill} />}
            {selected && <circle cx={cx} cy={cy} r={radius} fill="none" stroke="var(--color-accent)" strokeWidth={Math.max(2, pitch * 0.07)} />}
          </g>
        );
      })}
    </svg>
  );
}
