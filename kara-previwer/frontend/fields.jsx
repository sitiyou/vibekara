import React, { useEffect, useRef, useState } from "react";
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

function NumericRange({ id, field, value, change, onDraft, onCommit, referenceSize }) {
  const input = useRef(null);
  const [draft, setDraft] = useState(null);

  useEffect(() => {
    const slider = input.current;
    function commit() {
      const next = slider.valueAsNumber;
      setDraft(null);
      onDraft?.(null);
      if (onCommit) onCommit(next);
      else if (next !== value) change(next);
    }
    slider.addEventListener("change", commit);
    return () => slider.removeEventListener("change", commit);
  }, [change, onDraft, onCommit, value]);

  const shown = draft ?? value;
  const pct =
    100 * Math.min(1, Math.max(0, (shown - field.low) / (field.high - field.low || 1)));

  return (
    <>
      <input
        ref={input}
        id={id}
        className="studio-range"
        type="range"
        min={field.low}
        max={field.high}
        step={field.step || (field.kind === "int" ? 1 : 0.01)}
        value={shown}
        style={{ "--range-progress": pct + "%" }}
        onChange={(event) => {
          if (event.nativeEvent.type === "input") {
            const next = event.currentTarget.valueAsNumber;
            setDraft(next);
            onDraft?.(next);
          }
        }}
      />
      <output htmlFor={id}>
        {shown}
        {field.suffix}
        {referenceSize != null && ` · ${Math.round((shown * referenceSize) / 100)} px`}
      </output>
    </>
  );
}

export function Field({
  field: f,
  value,
  change,
  fonts,
  sample,
  onDraft,
  onCommit,
  referenceSize,
  compact,
}) {
  const id = "field-" + f.name;
  const [query, setQuery] = useState("");
  let control;

  if (
    fonts ||
    f.font ||
    ["font", "fontname", "font_family"].includes(f.name.toLowerCase())
  ) {
    const options = fonts || [
      ...new Set([f.default, "Noto Serif CJK JP", "Noto Sans CJK JP"]),
    ];
    control = compact ? (
      <Select
        items={options.map((name) => ({ value: name, label: name }))}
        value={value}
        onValueChange={(next) => {
          if (next != null) change(next);
        }}
      >
        <SelectTrigger id={id} aria-label={f.caption}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent align="start" alignItemWithTrigger={false}>
          {options.map((name) => (
            <SelectItem key={name} value={name}>
              <span className="property-font-option">
                {name}
                {sample && (
                  <span style={{ fontFamily: JSON.stringify(name) }}>{sample}</span>
                )}
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    ) : (
      <div className="font-list">
        {options.length > 6 && (
          <input
            className="studio-input"
            type="search"
            aria-label="筛选字体候选"
            placeholder="筛选字体…"
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
              <span>{name}</span>
              {sample && (
                <span style={{ fontFamily: JSON.stringify(name) }}>{sample}</span>
              )}
            </button>
          ))}
      </div>
    );
  } else if (f.kind === "choice") {
    const items = f.choices.map((val, i) => ({
      value: val,
      label: f.labels?.[i] ?? val,
    }));
    control =
      !compact && items.length <= 3 ? (
        <div className="segmented segmented-sm">
          {items.map((item) => (
            <button
              key={item.value}
              type="button"
              aria-pressed={value === item.value}
              onClick={() => change(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
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
    const brightness = (
      <div className="color-lightness">
        <label htmlFor={id}>亮度</label>
        <input
          id={id}
          className="studio-range"
          aria-label={f.caption + "亮度"}
          type="range"
          min="0"
          max="255"
          value={peak}
          style={{ "--range-progress": (100 * peak) / 255 + "%" }}
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
      </div>
    );
    control = (
      <ColorPicker
        id={id + "-color"}
        color={"#" + value}
        extra={brightness}
        onChange={(c) => {
          const next = rgb(c);
          if (next !== value) change(next);
        }}
      />
    );
  } else if (f.kind === "bool") {
    control = (
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={!!value}
        className="studio-switch"
        onClick={() => change(!value)}
      >
        <span className="studio-switch-thumb" />
      </button>
    );
  } else if (["float", "int"].includes(f.kind)) {
    control = (
      <NumericRange
        id={id}
        field={f}
        value={value}
        change={change}
        onDraft={onDraft}
        onCommit={onCommit}
        referenceSize={referenceSize}
      />
    );
  } else {
    control = (
      <input
        id={id}
        className="studio-input"
        value={value}
        onChange={(e) => change(e.target.value)}
      />
    );
  }

  return (
    <div className="field" data-kind={f.kind}>
      <label htmlFor={f.kind === "color" ? id + "-color" : id}>{f.caption}</label>
      <div className="field-control">{control}</div>
    </div>
  );
}
