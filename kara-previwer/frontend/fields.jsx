import React, { useEffect, useRef, useState } from "react";
import { HaloSegmented } from "./cult/halo-segmented";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./cult/base-select";
import { ColorPicker } from "./cult/color-picker";

function rgb(color) {
  const ctx = document.createElement("canvas").getContext("2d");
  ctx.fillStyle = color;
  return ctx.fillStyle.slice(1).toUpperCase();
}

function NumericRange({ id, field, value, change, onDraft, referenceSize }) {
  const input = useRef(null);
  const [draft, setDraft] = useState(null);
  useEffect(() => {
    const slider = input.current;
    // The browser's change event commits a range gesture. React's onChange
    // also handles input events while the thumb is moving.
    function commit() {
      const next = slider.valueAsNumber;
      setDraft(null);
      onDraft?.(null);
      if (next !== value) change(next);
    }
    slider.addEventListener("change", commit);
    return () => slider.removeEventListener("change", commit);
  }, [change, onDraft, value]);
  const shown = draft ?? value;
  return (
    <>
      <input
        ref={input}
        id={id}
        type="range"
        min={field.low}
        max={field.high}
        step={field.step || (field.kind === "int" ? 1 : 0.01)}
        value={shown}
        onChange={(event) => {
          if (event.nativeEvent.type === "input") {
            const next = event.currentTarget.valueAsNumber;
            setDraft(next);
            onDraft?.(next);
          }
        }}
      />
      <output htmlFor={id}>
        {shown}{field.suffix}
        {referenceSize != null && ` · ${Math.round(shown * referenceSize / 100)} px`}
      </output>
    </>
  );
}

export function Field({ field: f, value, change, fonts, sample, onDraft, referenceSize }) {
  const id = "field-" + f.name;
  const [query, setQuery] = useState("");
  let control;
  if (
    fonts ||
    ["font", "fontname", "font_family"].includes(f.name.toLowerCase())
  ) {
    const options = fonts || [
      ...new Set([f.default, "Noto Serif CJK JP", "Noto Sans CJK JP"]),
    ];
    control = (
      <div className="font-list">
        {options.length > 6 && (
          <input
            type="search"
            aria-label="筛选字体候选"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        )}
        {options
          .filter((name) => name.toLowerCase().includes(query.toLowerCase()))
          .map((name) => (
            <button
              type="button"
              key={name}
              aria-pressed={value === name}
              onClick={() => change(name)}
            >
              {name}
              {sample && (
                <span style={{ fontFamily: JSON.stringify(name) }}>
                  {sample}
                </span>
              )}
            </button>
          ))}
      </div>
    );
  } else if (f.kind === "choice") {
    const items = f.choices.map((value, i) => ({
      value,
      label: f.labels?.[i] ?? value,
    }));
    control =
      items.length <= 3 ? (
        <HaloSegmented items={items} value={value} onValueChange={change} />
      ) : (
        <Select items={items} value={value} onValueChange={change}>
          <SelectTrigger id={id}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="start" alignItemWithTrigger={false}>
            {items.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
  } else if (f.kind === "color") {
    const components = value.match(/../g).map((v) => parseInt(v, 16));
    const peak = Math.max(...components);
    const base = peak
      ? components
      : f.default.match(/../g).map((v) => parseInt(v, 16));
    control = (
      <>
        <ColorPicker
          color={"#" + value}
          onChange={(c) => {
            const next = rgb(c);
            if (next !== value) change(next);
          }}
        />
        <label htmlFor={id}>亮度</label>
        <input
          id={id}
          aria-label={f.caption + "亮度"}
          type="range"
          min="0"
          max="255"
          value={peak}
          onChange={(e) =>
            change(
              base
                .map((c) =>
                  Math.round(
                    (Math.max(...base) ? c / Math.max(...base) : 1) *
                      Number(e.target.value),
                  )
                    .toString(16)
                    .padStart(2, "0"),
                )
                .join("")
                .toUpperCase(),
            )
          }
        />
      </>
    );
  } else if (f.kind === "bool") {
    control = (
      <input
        id={id}
        type="checkbox"
        checked={value}
        onChange={(e) => change(e.target.checked)}
      />
    );
  } else if (["float", "int"].includes(f.kind)) {
    control = (
      <NumericRange
        id={id}
        field={f}
        value={value}
        change={change}
        onDraft={onDraft}
        referenceSize={referenceSize}
      />
    );
  } else
    control = (
      <input id={id} value={value} onChange={(e) => change(e.target.value)} />
    );
  return (
    <div className="field">
      <label htmlFor={id}>{f.caption}</label>
      {control}
    </div>
  );
}
