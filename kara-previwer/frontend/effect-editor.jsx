import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  Check,
  ChevronRight,
  GripVertical,
  Layers3,
  Plus,
  Search,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { componentValue, makeNode } from "./composition";
import { Parameter, targets, title } from "./composition-fields";
import { propertyKinds } from "./properties";
import { MotionPreview } from "./preview-cards";
import { occupants, placeEffect } from "./effect-placement";
import "./effect-editor.css";

export const slotNames = {
  entry: "入场",
  exit: "退场",
  transition: "过渡",
  highlight: "走字",
  front: "走字前沿",
  flash: "起音闪光",
  effects: "动效",
  decoration: "节拍装饰",
  particles: "粒子",
  material: "材质",
  glow: "辉光",
  extrusion: "立体",
  cue: "倒数提示",
};

const LAYERED_CATEGORY = "__layered__";

export function trackEffectItems(graph, track) {
  if (!graph || !track) return [];
  return graph.groups
    .filter((group) => group.track === track)
    .flatMap((group) =>
      group.components
        .filter((node) => !propertyKinds.has(node.component))
        .map((node) => ({ group, node })),
    );
}

function stackPosition(event, layers) {
  const rows = event.currentTarget.querySelectorAll("[data-layer]");
  for (const [index, row] of rows.entries()) {
    const box = row.getBoundingClientRect();
    const fraction = (event.clientY - box.top) / box.height;
    if (fraction < 0.5) return { item: layers[index], side: "before" };
  }
  if (layers.length) return { item: layers.at(-1), side: "after" };
}

/* ==========================================================================
   Persistent Left Effects Rack (always visible under monitor in Edit Mode)
   ========================================================================== */
export function EffectsRack({
  graph,
  schema,
  tracks,
  track,
  onTrackChange,
  selectedId,
  disabled,
  onInspect,
  onRemove,
  onReorder,
}) {
  const [dragNode, setDragNode] = useState(null);
  const [marker, setMarker] = useState(null);

  if (!tracks || !Object.keys(tracks).length) return null;

  const trackKeys = Object.keys(tracks);
  const activeTrack = tracks[track] ? track : trackKeys[0];
  const items = trackEffectItems(graph, activeTrack);
  const singles = items.filter(({ node }) => !schema[node.component]?.repeatable);
  const layers = items.filter(({ node }) => schema[node.component]?.repeatable);

  function handleLayerDrag(event, commit) {
    if (!dragNode || disabled) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    const position = stackPosition(event, layers);
    if (commit) {
      if (position && position.item.node.id !== dragNode.id) {
        onReorder(dragNode, position);
      }
      setDragNode(null);
      setMarker(null);
    } else {
      setMarker(position ?? null);
    }
  }

  return (
    <section className="effects-rack" aria-label="当前已启用特效">
      <div className="effects-rack-header">
        <span className="effects-rack-title">
          <Layers3 />
          当前效果（{items.length}）
        </span>
        {trackKeys.length > 1 && (
          <div className="segmented segmented-sm" aria-label="效果声部">
            {Object.entries(tracks).map(([id, info]) => (
              <button
                key={id}
                type="button"
                aria-pressed={id === activeTrack}
                onClick={() => onTrackChange(id)}
              >
                {info.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="effects-rack-body">
        <div className="rack-section">
          <div className="rack-section-label">
            <span>单选槽位</span>
          </div>
          {singles.length ? (
            <ul className="rack-singles">
              {singles.map(({ node }) => {
                const spec = schema[node.component];
                if (!spec) return null;
                return (
                  <li
                    key={node.id}
                    className="rack-item"
                    data-active={node.id === selectedId}
                  >
                    <button
                      type="button"
                      className="rack-choice"
                      onClick={() => onInspect(node)}
                      title={`调整 ${title(spec.label)}`}
                    >
                      <span className="rack-slot">{slotNames[spec.slot]}</span>
                      <span className="rack-name">{title(spec.label)}</span>
                      {node.target !== "track" && (
                        <span className="rack-target">{targets[node.target]}</span>
                      )}
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger-ghost btn-icon btn-sm"
                      disabled={disabled}
                      aria-label={"移除 " + title(spec.label)}
                      title={"移除 " + title(spec.label)}
                      onClick={() => onRemove(node)}
                    >
                      <Trash2 />
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="rack-empty">尚未启用单选效果</p>
          )}
        </div>

        <div
          className="rack-section"
          onDragOver={(e) => handleLayerDrag(e, false)}
          onDrop={(e) => handleLayerDrag(e, true)}
          onDragLeave={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget)) setMarker(null);
          }}
        >
          <div className="rack-section-label">
            <span>叠加层</span>
          </div>
          {layers.length ? (
            <ol className="rack-layers">
              {layers.map((item, index) => {
                const { node } = item;
                const spec = schema[node.component];
                if (!spec) return null;
                return (
                  <li
                    key={node.id}
                    className="rack-item"
                    data-layer=""
                    data-active={node.id === selectedId}
                    data-marker={
                      dragNode && marker?.item?.node.id === node.id
                        ? marker.side
                        : undefined
                    }
                  >
                    <span
                      className="rack-grip"
                      draggable={!disabled}
                      title="拖动调整叠加顺序"
                      onDragStart={(e) => {
                        e.dataTransfer.setData("text/plain", node.id);
                        e.dataTransfer.effectAllowed = "move";
                        setDragNode(node);
                      }}
                      onDragEnd={() => {
                        setDragNode(null);
                        setMarker(null);
                      }}
                    >
                      <GripVertical />
                    </span>
                    <button
                      type="button"
                      className="rack-choice"
                      onClick={() => onInspect(node)}
                    >
                      <span className="rack-name">{title(spec.label)}</span>
                      <span className="rack-target">{targets[node.target]}</span>
                    </button>
                    <div className="rack-item-actions">
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon btn-sm"
                        aria-label="上移"
                        title="上移"
                        disabled={disabled || index === 0}
                        onClick={() =>
                          onReorder(node, { item: layers[index - 1], side: "before" })
                        }
                      >
                        <ArrowUp />
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon btn-sm"
                        aria-label="下移"
                        title="下移"
                        disabled={disabled || index === layers.length - 1}
                        onClick={() =>
                          onReorder(node, { item: layers[index + 1], side: "after" })
                        }
                      >
                        <ArrowDown />
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger-ghost btn-icon btn-sm"
                        disabled={disabled}
                        aria-label={"移除 " + title(spec.label)}
                        title={"移除 " + title(spec.label)}
                        onClick={() => onRemove(node)}
                      >
                        <Trash2 />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="rack-empty">尚未添加叠加动效或粒子</p>
          )}
        </div>
      </div>
    </section>
  );
}

/* ==========================================================================
   Inspector Subpage
   ========================================================================== */
function Inspector({ node, spec, sample, disabled, change, retarget, heading }) {
  const fields = Object.entries(spec.parameters)
    .filter(([name]) => !node.fields || node.fields.includes(name))
    .sort(
      ([a], [b]) =>
        (node.controls[a]?.group ?? "").localeCompare(
          node.controls[b]?.group ?? "",
        ) || (node.controls[a]?.order ?? 0) - (node.controls[b]?.order ?? 0),
    );

  function renderParams(entries) {
    let lastGroup = "";
    return entries.map(([name, definition]) => {
      const options = node.controls[name] ?? {};
      const group = options.group ?? "";
      const groupHeading =
        group && group !== lastGroup ? (
          <h4 className="fx-inspector-group-title">{group}</h4>
        ) : null;
      lastGroup = group;
      return (
        <div key={name}>
          {groupHeading}
          <Parameter
            id={node.id}
            name={name}
            definition={definition}
            value={node.values[name]}
            options={options}
            live={!!node.bindings[name]}
            draft={(value) => value != null && change(name, value, "live")}
            commit={(value) => change(name, value)}
            sample={sample}
          />
        </div>
      );
    });
  }

  const mainFields = fields.filter(([, def]) => !def.advanced);
  const advFields = fields.filter(([, def]) => def.advanced);

  return (
    <section aria-label={heading} style={{ display: "grid", gap: "12px" }}>
      <div className="fx-inspector-head">
        <h3 tabIndex={-1}>{heading}</h3>
        {spec.targets.length > 1 && (
          <div className="segmented segmented-sm" aria-label="作用对象">
            {spec.targets.map((target) => (
              <button
                key={target}
                type="button"
                aria-pressed={node.target === target}
                disabled={disabled}
                onClick={() => retarget(target)}
              >
                {targets[target]}
              </button>
            ))}
          </div>
        )}
      </div>

      <fieldset disabled={disabled} className="fx-inspector-fields">
        {renderParams(mainFields)}
        {advFields.length > 0 && (
          <details className="studio-details">
            <summary>
              <ChevronRight />
              更多参数
            </summary>
            <div className="studio-details-body">{renderParams(advFields)}</div>
          </details>
        )}
      </fieldset>
    </section>
  );
}

/* ==========================================================================
   Right Panel: Flattened Effects Catalog & Inspector Subpage
   ========================================================================== */
export function EffectsPanel({
  graph,
  schema,
  previews,
  tracks,
  track,
  selectedId,
  onSelectId,
  trialNode,
  onAudition,
  onFinishTrial,
  onPlace,
  edit,
  sample,
  disabled,
}) {
  const catalogEntries = Object.entries(schema).filter(
    ([kind]) => !propertyKinds.has(kind),
  );
  const singleSlots = [
    ...new Set(
      catalogEntries
        .filter(([, spec]) => !spec.repeatable)
        .map(([, spec]) => spec.slot),
    ),
  ];
  const hasLayered = catalogEntries.some(([, spec]) => spec.repeatable);

  const [category, setCategory] = useState(() =>
    singleSlots.includes("highlight")
      ? "highlight"
      : singleSlots[0] ?? LAYERED_CATEGORY,
  );
  const [query, setQuery] = useState("");
  const [target, setTarget] = useState("body");
  const panelRef = useRef(null);

  const trackKeys = Object.keys(tracks);
  const activeTrack = tracks[track] ? track : trackKeys[0];
  const items = trackEffectItems(graph, activeTrack);
  const scope = tracks[activeTrack];

  const activeNode =
    selectedId === "__trial__" && trialNode
      ? trialNode
      : items.find(({ node }) => node.id === selectedId)?.node;

  useEffect(() => {
    if (activeNode) panelRef.current?.querySelector("h3")?.focus();
  }, [activeNode?.id]);

  // Installed slots set for showing dot indicator on category chips
  const installedSlots = new Set(
    items
      .filter(({ node }) => !schema[node.component]?.repeatable)
      .map(({ node }) => schema[node.component]?.slot),
  );
  const hasInstalledLayered = items.some(
    ({ node }) => schema[node.component]?.repeatable,
  );

  // Inspector Subpage View
  if (activeNode && schema[activeNode.component]) {
    const isTrial = selectedId === "__trial__" && trialNode?.id === activeNode.id;
    const spec = {
      ...schema[activeNode.component],
      targets: schema[activeNode.component].targets.filter(
        (id) => id !== "ruby" || scope?.ruby || activeNode.target === "ruby",
      ),
    };
    return (
      <div
        ref={panelRef}
        className="fx-inspector-page"
        onKeyDown={(e) => {
          if (e.key === "Escape" && !e.defaultPrevented) {
            onSelectId(null);
          }
        }}
      >
        <div className="fx-inspector-nav">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onSelectId(null)}
          >
            <ArrowLeft />
            返回特效库
          </button>
          <span
            className={"fx-inspector-context" + (isTrial ? " is-trial" : "")}
          >
            {isTrial ? "试放调参" : "已启用"} ·{" "}
            {slotNames[spec.slot] ?? spec.slot} · {targets[activeNode.target]}
          </span>
        </div>

        <Inspector
          node={activeNode}
          spec={spec}
          sample={sample}
          disabled={disabled}
          heading={title(spec.label)}
          change={(key, value, mode) => {
            if (isTrial) {
              onAudition({
                ...activeNode,
                values: { ...activeNode.values, [key]: value },
              });
            } else {
              edit(componentValue(graph, activeNode.id, key, value), mode);
            }
          }}
          retarget={(id) => {
            const updated = { ...activeNode, target: id };
            if (isTrial) onAudition(updated);
            else onPlace({ node: updated });
          }}
        />

        {!Object.keys(spec.parameters).length && (
          <p className="fx-empty">此效果使用固定参数，无需额外调节。</p>
        )}
      </div>
    );
  }

  // Flattened Single-Layer Catalog View
  const search = query.trim().toLowerCase();
  const visible = search
    ? catalogEntries.filter(([kind, spec]) =>
        (kind + " " + title(spec.label) + " " + (slotNames[spec.slot] ?? ""))
          .toLowerCase()
          .includes(search),
      )
    : category === LAYERED_CATEGORY
      ? catalogEntries.filter(([, spec]) => spec.repeatable)
      : catalogEntries.filter(
          ([, spec]) => !spec.repeatable && spec.slot === category,
        );

  const showRubyScope =
    scope?.ruby && visible.some(([, spec]) => spec.targets.includes("ruby"));

  return (
    <div className="fx-catalog">
      <div className="fx-catalog-top">
        <label className="fx-search">
          <Search />
          <input
            type="search"
            value={query}
            aria-label="搜索全部特效"
            placeholder="搜索全部特效…"
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>

        {showRubyScope && (
          <div className="segmented segmented-sm" aria-label="字形效果作用对象">
            {["body", "ruby"].map((id) => (
              <button
                key={id}
                type="button"
                aria-pressed={id === target}
                onClick={() => setTarget(id)}
              >
                {targets[id]}
              </button>
            ))}
          </div>
        )}
      </div>

      {!search && (
        <nav className="fx-categories" aria-label="特效分类">
          {singleSlots.map((slotId) => (
            <button
              key={slotId}
              type="button"
              className="fx-chip"
              aria-pressed={category === slotId}
              onClick={() => setCategory(slotId)}
            >
              {slotNames[slotId] ?? slotId}
              {installedSlots.has(slotId) && <span className="fx-chip-dot" />}
            </button>
          ))}
          {hasLayered && (
            <button
              type="button"
              className="fx-chip"
              aria-pressed={category === LAYERED_CATEGORY}
              onClick={() => setCategory(LAYERED_CATEGORY)}
            >
              可叠加动效
              {hasInstalledLayered && <span className="fx-chip-dot" />}
            </button>
          )}
        </nav>
      )}

      {visible.length ? (
        <ul className="fx-cards">
          {visible.map(([kind, spec]) => {
            const scopeTarget = spec.targets.includes(target)
              ? target
              : spec.targets[0];
            const conflicts = occupants(items, schema, kind, scopeTarget);
            const installed = conflicts.find(
              ({ node }) =>
                node.component === kind && node.target === scopeTarget,
            );
            const isTrialing =
              trialNode?.component === kind &&
              trialNode?.target === scopeTarget;
            const actionLabel = installed
              ? "调参"
              : spec.repeatable
                ? "叠加"
                : conflicts.length
                  ? "替换"
                  : "应用";

            const handleCardClick = () => {
              if (disabled) return;
              if (installed) {
                onFinishTrial();
                onSelectId(installed.node.id);
              } else if (isTrialing) {
                onSelectId("__trial__");
              } else {
                onAudition({ ...makeNode(kind, spec), target: scopeTarget });
              }
            };

            return (
              <li
                key={kind}
                className="fx-card"
                data-installed={!!installed}
                data-trial={isTrialing}
              >
                <button
                  type="button"
                  className="fx-card-preview-btn"
                  onClick={handleCardClick}
                  title={
                    installed
                      ? `调整 ${title(spec.label)} 参数`
                      : isTrialing
                        ? "点击调整试放参数"
                        : `点击试放 ${title(spec.label)}`
                  }
                >
                  {isTrialing ? (
                    <span className="fx-card-badge is-trial">试放中</span>
                  ) : installed ? (
                    <span className="fx-card-badge is-installed">已启用</span>
                  ) : null}
                  <MotionPreview
                    {...previews[kind]}
                    label={title(spec.label)}
                  />
                </button>

                <div className="fx-card-footer">
                  <div className="fx-card-meta">
                    <strong title={title(spec.label)}>
                      {title(spec.label)}
                    </strong>
                    <small>
                      {search && (spec.repeatable ? "可叠加 · " : "")}
                      {slotNames[spec.slot]} · {targets[scopeTarget]}
                    </small>
                  </div>
                  <button
                    type="button"
                    className={
                      "btn btn-sm " +
                      (installed ? "btn-ghost" : isTrialing ? "btn-warn" : "")
                    }
                    disabled={!installed && disabled}
                    onClick={() => {
                      if (installed) {
                        onFinishTrial();
                        onSelectId(installed.node.id);
                      } else if (isTrialing) {
                        onPlace({ node: trialNode });
                      } else {
                        onPlace({ kind, target: scopeTarget });
                      }
                    }}
                  >
                    {installed ? (
                      <SlidersHorizontal />
                    ) : spec.repeatable ? (
                      <Plus />
                    ) : (
                      <Check />
                    )}
                    {actionLabel}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="fx-empty">没有匹配的特效</p>
      )}
    </div>
  );
}
