// The server owns validation and cache keys. The player only needs to know
// whether a local edit changes the component structure or a bound GPU value.
function serialize(composition, structural) {
  const data = structural && composition ? {version: composition.version, groups: composition.groups} : composition;
  return JSON.stringify(data, (key, value) => {
    if (structural && key === "components") {
      return value.map(node => ({
        ...node,
        values: Object.fromEntries(Object.entries(node.values).filter(([name]) => !node.bindings[name])),
      }));
    }
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return Object.fromEntries(Object.keys(value).sort().map(name => [name, value[name]]));
    }
    return value;
  });
}

export const structureKey = composition => serialize(composition, true);
export const compositionKey = composition => serialize(composition, false);

export function compositionValues(composition) {
  return Object.fromEntries((composition?.groups ?? []).flatMap(group =>
    group.components.flatMap(node => Object.entries(node.bindings).map(([name, id]) => [id, node.values[name]]))));
}

export function componentValue(composition, owner, name, value) {
  const source = composition.groups.flatMap(group => group.components).find(node => node.id === owner);
  const shared = source.bindings[name];
  return {
    ...composition,
    groups: composition.groups.map(group => ({
      ...group,
      components: group.components.map(node => {
        const field = node.id === owner ? name
          : shared && Object.keys(node.bindings).find(key => node.bindings[key] === shared);
        return field ? {...node, values: {...node.values, [field]: value}} : node;
      }),
    })),
  };
}

export function makeNode(component, definition) {
  const id = "n" + crypto.randomUUID().replaceAll("-", "");
  const fields = Object.entries(definition.parameters);
  return {
    id, component, target: definition.targets[0],
    values: Object.fromEntries(fields.map(([name, field]) => [name, field.default])),
    bindings: Object.fromEntries(fields.filter(([, field]) => field.live)
      .map(([name], index) => [name, `${id}_${index}`])),
    controls: {},
  };
}
