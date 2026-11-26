// Locations refer to existing graph nodes so hidden properties and original groups survive edits.
export function occupants(items, schema, kind, target, exceptId) {
  const spec = schema[kind];
  if (spec.repeatable) return [];
  return items.filter(({node}) => node.id !== exceptId && schema[node.component].slot === spec.slot &&
    (node.target === target || node.target === "track" || target === "track"));
}

export function placeEffect(graph, track, items, schema, node, location) {
  const conflicts = occupants(items, schema, node.component, node.target, node.id);
  const current = items.find(item => item.node.id === node.id);
  const layers = items.filter(item => schema[item.node.component].repeatable);
  const anchor = location?.item ?? current ?? conflicts[0] ?? (schema[node.component].repeatable && layers.at(-1));
  const group = anchor?.group ?? items[0]?.group ?? graph.groups.find(group => group.track === track)
    ?? {id: "g" + crypto.randomUUID().replaceAll("-", ""), track, label: "特效", components: []};
  const removed = new Set([node.id, ...conflicts.map(({node}) => node.id)]);
  if (location?.side === "replace") removed.add(anchor.node.id);
  let index = anchor ? group.components.indexOf(anchor.node) : group.components.length;
  if (location?.side === "after" || (!location && !current && !conflicts.length && anchor)) index++;
  const keep = item => !removed.has(item.id);
  const groups = graph.groups.includes(group) ? graph.groups : [...graph.groups, group];
  return {...graph, groups: groups.map(item => ({...item, components: item === group
    ? [...item.components.slice(0, index).filter(keep), node, ...item.components.slice(index).filter(keep)]
    : item.components.filter(keep)}))};
}
