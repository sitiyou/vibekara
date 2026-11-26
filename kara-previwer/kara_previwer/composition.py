"""Validate and split editable candidate compositions at the preview boundary."""

import re
from math import isfinite

IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}")
PROPERTY_KINDS = {
    "typography", "lyric-colors", "outline", "glyph-blur",
    "offset-shadow", "layout", "karaoke-rows", "ruby-layout",
}


def resolved_value(field, value):
    bounds = field["bounds"]
    match field["kind"]:
        case "number" | "integer" if type(value) in (int, float) and isfinite(value):
            if bounds is None or bounds[0] <= value <= bounds[1]:
                if field["kind"] == "number":
                    return float(value)
                if int(value) == value:
                    return int(value)
        case "color" if isinstance(value, str) and re.fullmatch(r"[0-9A-Fa-f]{6}", value):
            return value.upper()
        case "boolean" if type(value) is bool:
            return value
        case "text" if isinstance(value, str) and value.strip() and len(value) <= 160:
            return value
        case "choice" if isinstance(value, str) and value in field["choices"]:
            return value
    raise ValueError(f"无效参数：{field['label']}")


def normalize(proposal, composition):
    """Validate and return a portable, complete candidate graph."""
    schema = proposal.get("component_schema")
    if schema is None:
        if composition is not None:
            raise ValueError("当前方案没有可编辑的组件")
        return None
    if (
        not isinstance(composition, dict) or set(composition) - {"version", "groups", "properties"}
        or not {"version", "groups"} <= composition.keys()
        or type(composition["version"]) is not int or composition["version"] != 1
    ):
        raise ValueError("未知的组件组合版本")
    groups = composition["groups"]
    if not isinstance(groups, list) or len(groups) > 32:
        raise ValueError("组件组过多")
    ids = set()
    occupied = set()
    shared = {}
    reserved = {field["name"] for field in proposal["parameters"]}

    def identifier(value):
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value) or value in ids:
            raise ValueError("无效或重复的节点 ID")
        ids.add(value)
        return value

    normalized = []
    for group in groups:
        if not isinstance(group, dict) or set(group) != {"id", "label", "track", "components"}:
            raise ValueError("组件组需要名称、轨道和组件")
        group_id = identifier(group["id"])
        label, track, nodes = group["label"], group["track"], group["components"]
        if (
            not isinstance(label, str) or not label.strip() or len(label) > 80
            or not isinstance(track, str) or track not in proposal["composition_tracks"]
        ):
            raise ValueError("无效的组件组名称或轨道")
        if not isinstance(nodes, list) or len(nodes) > 64:
            raise ValueError("组内组件过多")
        components = []
        for node in nodes:
            if not isinstance(node, dict) or set(node) - {"id", "component", "target", "values", "bindings", "controls", "fields"}:
                raise ValueError("无效的组件")
            node_id = identifier(node.get("id"))
            component = node.get("component")
            spec = schema.get(component) if isinstance(component, str) else None
            target = node.get("target", spec["targets"][0] if spec else "")
            if spec is None or target not in spec["targets"]:
                raise ValueError("该组件无法应用到所选目标")
            slot = (track, spec["slot"], target)
            if not spec["repeatable"] and any(
                other_track == track and other_slot == spec["slot"]
                and (other_target == target or other_target == "track" or target == "track")
                for other_track, other_slot, other_target in occupied
            ):
                raise ValueError("该位置只能放一个组件")
            occupied.add(slot)
            fields = spec["parameters"]
            values, bindings, controls = (node.get(key, {}) for key in ("values", "bindings", "controls"))
            if any(not isinstance(data, dict) or data.keys() - fields.keys() for data in (values, bindings, controls)):
                raise ValueError("组件包含未知参数")
            visible = node.get("fields")
            if "fields" in node and (
                not isinstance(visible, list)
                or any(not isinstance(name, str) or name not in fields for name in visible)
                or len(set(visible)) != len(visible)
                or bindings.keys() - set(visible)
            ):
                raise ValueError("公开参数需来自组件声明，并包含所有实时绑定")
            if controls.keys() - bindings.keys():
                raise ValueError("控件设置需要绑定参数 ID")
            result = {}
            custom = {}
            for name, field in fields.items():
                value = resolved_value(field, values.get(name, field["default"]))
                result[name] = value
                if name not in bindings:
                    continue
                bound = bindings[name]
                if not field["live"] or not isinstance(bound, str) or not IDENTIFIER.fullmatch(bound) or bound in reserved:
                    raise ValueError("无效的实时参数绑定")
                control = controls.get(name, {})
                if not isinstance(control, dict) or control.keys() - {"bounds", "step", "label", "group", "order"}:
                    raise ValueError("无效的控件设置")
                bounds = control.get("bounds") if control.get("bounds") is not None else field["bounds"]
                if bounds is not None and (
                    not isinstance(bounds, (tuple, list)) or len(bounds) != 2 or field["bounds"] is None
                    or any(type(v) not in (int, float) for v in bounds)
                    or not field["bounds"][0] <= bounds[0] < bounds[1] <= field["bounds"][1]
                    or not bounds[0] <= value <= bounds[1]
                ):
                    raise ValueError("实时参数范围超出组件允许范围")
                step = control.get("step") if control.get("step") is not None else field["step"]
                if step is not None and (not bounds or type(step) not in (int, float) or not isfinite(step) or step <= 0):
                    raise ValueError("无效的实时参数步长")
                if (
                    any(not isinstance(control.get(key, ""), str) or len(control.get(key, "")) > 80
                        for key in ("label", "group"))
                    or type(control.get("order", 0)) is not int
                ):
                    raise ValueError("无效的控件标签或顺序")
                resolved = {
                    "bounds": list(bounds) if bounds is not None else None,
                    "step": step, "label": control.get("label") or field["label"],
                    "group": control.get("group", ""), "order": control.get("order", 0),
                }
                custom[name] = resolved
                identity = (field["kind"], field["unit"], value, resolved)
                if shared.setdefault(bound, identity) != identity:
                    raise ValueError("共享参数需要相同的值、类型和控件设置")
            item = {
                "id": node_id, "component": component, "target": target, "values": result,
                "bindings": bindings, "controls": custom,
            }
            if visible is not None:
                item["fields"] = visible
            components.append(item)
        normalized.append({"id": group_id, "label": label, "track": track, "components": components})
    result = {"version": 1, "groups": normalized}
    if "properties" in composition:
        properties = composition["properties"]
        if not isinstance(properties, dict) or properties.keys() - ({"$common"} | proposal["composition_tracks"].keys()):
            raise ValueError("未知的属性范围")
        scopes = {}
        for scope, edits in properties.items():
            if not isinstance(edits, dict):
                raise TypeError("无效的属性覆盖")
            values = {}
            for key, value in edits.items():
                parts = key.split(".")
                if len(parts) != 3:
                    raise ValueError("未知属性")
                kind, target, field = parts
                spec = schema.get(kind)
                if kind not in PROPERTY_KINDS or not spec or target not in spec["targets"] or field not in spec["parameters"]:
                    raise ValueError("未知属性")
                values[key] = resolved_value(spec["parameters"][field], value)
            if values:
                scopes[scope] = values
        if scopes:
            result["properties"] = scopes
    return result


def material_values(composition):
    return {
        binding: node["values"][name]
        for group in (composition or {}).get("groups", [])
        for node in group["components"]
        for name, binding in node["bindings"].items()
    }


def structural_composition(proposal, composition):
    """Keep the preview cache and shader defaults independent of live values."""
    if composition is None:
        return None
    schema = proposal["component_schema"]
    groups = []
    defaults = {}
    for group in composition["groups"]:
        nodes = []
        for node in group["components"]:
            values = node["values"].copy()
            for name, binding in node["bindings"].items():
                default = schema[node["component"]]["parameters"][name]["default"]
                if bounds := node["controls"][name]["bounds"]:
                    default = max(bounds[0], min(bounds[1], default))
                values[name] = defaults.setdefault(binding, default)
            nodes.append({**node, "values": values})
        groups.append({**group, "components": nodes})
    return {"version": composition["version"], "groups": groups}
