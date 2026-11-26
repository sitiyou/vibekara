import { makeNode } from "./composition.js";

export const COMMON_SCOPE = "$common";

export const propertyKinds = new Set([
  "typography", "lyric-colors", "outline", "glyph-blur", "offset-shadow", "layout", "karaoke-rows", "ruby-layout",
]);

export function propertyNode(graph, track, kind, target) {
  const variants = ["layout", "karaoke-rows"].includes(kind) ? ["layout", "karaoke-rows"] : [kind];
  for (const group of graph.groups) {
    if (group.track !== track) continue;
    const node = group.components.find(node => variants.includes(node.component) && node.target === target);
    if (node) return {node, group};
  }
  return {};
}

export function authoredProperties(baseline, tracks, track, kind, target) {
  const settings = tracks[track]?.properties ?? {};
  const {node} = propertyNode(baseline, track, kind, target);
  const key = kind + "." + target;
  if (kind === "layout" && node?.component === "karaoke-rows" && !settings[key]) {
    return {rows: 2, alignment: "alternating", ...node.values};
  }
  return {...settings[key], ...(node?.component === kind ? node.values : {})};
}

export function matchingTracks(tracks, kind, target) {
  const reading = target === "ruby" || kind === "ruby-layout";
  return Object.keys(tracks).filter(track => !reading || tracks[track].ruby);
}

export function editProperty(graph, baseline, tracks, schema, scope, kind, target, field, value) {
  const prefix = kind + "." + target + ".";
  const key = prefix + field;
  const properties = {...graph.properties};
  const edits = {...properties[scope]};
  if (value === undefined) delete edits[key];
  else edits[key] = value;
  if (Object.keys(edits).length) properties[scope] = edits;
  else delete properties[scope];
  const next = {...graph, groups: graph.groups, ...(Object.keys(properties).length ? {properties} : {})};
  if (!Object.keys(properties).length) delete next.properties;
  const affected = scope === COMMON_SCOPE ? matchingTracks(tracks, kind, target) : [scope];

  for (const track of affected) {
    const {node, group} = propertyNode(next, track, kind, target);
    const original = propertyNode(baseline, track, kind, target).node;
    if (original?.fields && !original.fields.includes(field)) continue;
    const assignments = Object.fromEntries(Object.entries({
      ...properties[COMMON_SCOPE], ...properties[track],
    }).filter(([id]) => id.startsWith(prefix) && (!original?.fields || original.fields.includes(id.slice(prefix.length))))
      .map(([id, value]) => [id.slice(prefix.length), value]));
    if (!Object.keys(assignments).length) {
      if (group) {
        next.groups = next.groups.map(item => item === group ? {
          ...item, components: item.components.flatMap(component => component === node ? original ? [original] : [] : [component]),
        } : item).filter(item => item.components.length || baseline.groups.some(group => group.id === item.id));
      }
      continue;
    }

    const sameKind = node?.component === kind;
    const defaults = makeNode(kind, schema[kind]);
    const seeded = authoredProperties(baseline, tracks, track, kind, target);
    const values = Object.fromEntries(Object.entries(schema[kind].parameters).map(([name, definition]) => {
      const inherited = seeded[name] ?? definition.default;
      const [lo, hi] = definition.bounds ?? [];
      const normalized = lo === undefined ? inherited : Math.min(hi, Math.max(lo, inherited));
      return [name, assignments[name] ?? normalized];
    }));
    const updated = {...(sameKind ? node : defaults), target, values};
    if (group) {
      next.groups = next.groups.map(item => item === group ? {
        ...item, components: item.components.map(component => component === node ? updated : component),
      } : item);
    } else {
      const owner = next.groups.find(item => item.track === track);
      next.groups = owner ? next.groups.map(item => item === owner ? {
        ...item, components: [...item.components, updated],
      } : item) : [...next.groups, {
        id: "g" + crypto.randomUUID().replaceAll("-", ""), label: "属性", track, components: [updated],
      }];
    }
  }
  return next;
}
