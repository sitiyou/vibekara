import { useState } from "react";
import { ChevronRight, Compass } from "lucide-react";
import {
  COMMON_SCOPE,
  authoredProperties,
  editProperty,
  matchingTracks,
  propertyNode,
} from "./properties";
import { Parameter, targets, title } from "./composition-fields";

export function PropertyEditor({
  graph,
  baseline,
  tracks,
  schema,
  sample,
  edit,
  jumpTo,
  disabled,
}) {
  const [scope, setScope] = useState(COMMON_SCOPE);
  const [view, setView] = useState("body");

  const trackKeys = Object.keys(tracks);
  const selection = tracks[scope] ? scope : COMMON_SCOPE;
  const visibleTracks = selection === COMMON_SCOPE ? trackKeys : [selection];
  const hasRuby = visibleTracks.some((track) => tracks[track].ruby);
  const textTarget = hasRuby ? view : "body";
  const edited = graph.properties?.[selection] ?? {};

  function valuesFor(kind, target) {
    return visibleTracks
      .filter((track) => matchingTracks(tracks, kind, target).includes(track))
      .map((track) => {
        const { node } = propertyNode(graph, track, kind, target);
        return {
          track,
          fields: node?.fields,
          ...authoredProperties(baseline, tracks, track, kind, target),
          ...(node?.component === kind ? node.values : {}),
        };
      });
  }

  function properties(kind, inline = false) {
    const spec = schema[kind];
    if (!spec || (kind === "ruby-layout" && !hasRuby)) return null;
    const target = spec.targets.includes(textTarget)
      ? textTarget
      : spec.targets[0];
    const rows = valuesFor(kind, target);
    if (!rows.length) return null;

    const prefix = kind + "." + target + ".";
    const fields = Object.entries(spec.parameters).filter(([name]) =>
      rows.some((row) => !row.fields || row.fields.includes(name)),
    );
    const mainFields = fields.filter(([, field]) => !field.advanced);
    const advanced = fields.filter(([, field]) => field.advanced);

    const change = (name, value) =>
      edit(
        editProperty(
          graph,
          baseline,
          tracks,
          schema,
          selection,
          kind,
          target,
          name,
          value,
        ),
      );

    function controls(entries) {
      return entries.map(([name, definition]) => {
        const key = prefix + name;
        const source = selection === COMMON_SCOPE ? edited[key] : undefined;
        const currentValues = rows.map((row) => row[name]);
        const shown =
          source ??
          currentValues.find((value) => value !== undefined) ??
          definition.default;
        const mixed = source === undefined && new Set(currentValues).size > 1;
        return (
          <Parameter
            key={key}
            id={selection + "_" + kind + "_" + target}
            name={name}
            definition={definition}
            value={shown}
            sample={sample}
            mixed={mixed}
            commit={(value) => change(name, value)}
            reset={
              Object.hasOwn(edited, key)
                ? () => change(name, undefined)
                : undefined
            }
          />
        );
      });
    }

    if (inline) {
      return controls(
        kind === "typography"
          ? mainFields.filter(([name]) => name === "outline")
          : mainFields,
      );
    }

    const typography = kind === "typography";
    return (
      <section className="property-group" data-kind={kind} key={kind}>
        <div className="property-heading">
          <h3>{typography ? "字形" : title(spec.label)}</h3>
          {typography && sample && (
            <p
              className="property-sample"
              style={{
                fontFamily: rows[0]?.fontname && JSON.stringify(rows[0].fontname),
                fontWeight: rows[0]?.bold ? 700 : 400,
                fontStyle: rows[0]?.italic ? "italic" : "normal",
              }}
            >
              {sample}
            </p>
          )}
        </div>
        <div className="property-fields">
          {controls(
            typography
              ? mainFields.filter(([name]) => name !== "outline")
              : mainFields,
          )}
        </div>
        {!!advanced.length && (
          <details className="studio-details">
            <summary>
              <ChevronRight />
              {typography ? "更多字体设置" : "更多" + title(spec.label) + "设置"}
            </summary>
            <div className="studio-details-body">{controls(advanced)}</div>
          </details>
        )}
      </section>
    );
  }

  const active = tracks[selection];
  const showJump = active?.start != null;
  const showScopeBar = trackKeys.length > 1 || hasRuby;
  const ink = [
    properties("typography", true),
    properties("lyric-colors", true),
  ]
    .flat()
    .filter(Boolean);

  return (
    <div className="property-editor">
      {showScopeBar && (
        <div className="scope-bar" aria-label="样式作用范围">
          {trackKeys.length > 1 && (
            <div className="scope-group">
              <span className="scope-label">声部</span>
              <div className="segmented segmented-sm">
                <button
                  type="button"
                  aria-pressed={selection === COMMON_SCOPE}
                  onClick={() => setScope(COMMON_SCOPE)}
                >
                  共用
                </button>
                {Object.entries(tracks).map(([id, track]) => (
                  <button
                    key={id}
                    type="button"
                    aria-pressed={selection === id}
                    onClick={() => setScope(id)}
                  >
                    {track.label}
                  </button>
                ))}
              </div>
              {showJump && (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => jumpTo(active.start)}
                  title={"跳转到" + active.label + "出现位置"}
                >
                  <Compass />
                  跳到{active.label}
                </button>
              )}
            </div>
          )}

          {hasRuby && (
            <div className="scope-group">
              <span className="scope-label">文字对象</span>
              <div className="segmented segmented-sm" aria-label="文字对象">
                {["body", "ruby"].map((choice) => (
                  <button
                    key={choice}
                    type="button"
                    aria-pressed={textTarget === choice}
                    onClick={() => setView(choice)}
                  >
                    {targets[choice]}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <fieldset disabled={disabled} className="property-groups">
        {properties("typography")}
        {!!ink.length && (
          <section className="property-group" data-kind="ink">
            <div className="property-heading">
              <h3>描边与配色</h3>
            </div>
            <div className="property-fields">{ink}</div>
          </section>
        )}
        {["outline", "glyph-blur", "offset-shadow", "layout", "ruby-layout"].map(
          (kind) => properties(kind),
        )}
      </fieldset>
    </div>
  );
}
