from typing import Any

from jinja2 import StrictUndefined, nodes
from jinja2.sandbox import ImmutableSandboxedEnvironment

SEVERITIES = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
OPS = {"equals", "not_equals", "in", "not_in", "contains", "exists", "greater", "less", "gte", "lte"}


def matches(event: dict, conditions: list):
    for condition in conditions:
        field, op, expected = condition["field"], condition["op"], condition.get("value")
        current: Any = event
        for part in field.split("."):
            current = current.get(part) if isinstance(current, dict) else None
        if op == "exists":
            result = (current is not None) == bool(expected if expected is not None else True)
        elif op == "equals":
            result = current == expected
        elif op == "not_equals":
            result = current != expected
        elif op in {"in", "not_in"}:
            result = isinstance(expected, list) and current in expected
            if op == "not_in":
                result = not result
        elif op == "contains":
            result = (
                (isinstance(current, str) and isinstance(expected, str) and expected in current)
                or (isinstance(current, list) and expected in current)
                or (isinstance(current, dict) and isinstance(expected, str) and expected in current)
            )
        elif op in {"greater", "less", "gte", "lte"}:
            if field == "severity" and current in SEVERITIES and expected in SEVERITIES:
                current, expected = SEVERITIES.index(current), SEVERITIES.index(expected)
            if not isinstance(current, (int, float)) or not isinstance(expected, (int, float)):
                return False
            result = {
                "greater": current > expected,
                "less": current < expected,
                "gte": current >= expected,
                "lte": current <= expected,
            }[op]
        else:
            return False
        if not result:
            return False
    return True


class RestrictedEnvironment(ImmutableSandboxedEnvironment):
    def is_safe_attribute(self, obj, attr, value):
        return False

    def is_safe_callable(self, obj):
        return False


def render(template: str, event: dict, html=False):
    """Interpolation only: no loops, calls, arithmetic, imports, or arbitrary attributes."""
    if len(template) > 20000:
        raise ValueError("Template too long")
    env = RestrictedEnvironment(undefined=StrictUndefined, autoescape=html)
    env.globals.clear()
    env.filters = {k: v for k, v in env.filters.items() if k in {"escape", "e", "default", "upper", "lower"}}
    tree = env.parse(template)
    allowed = (
        nodes.Template,
        nodes.Output,
        nodes.TemplateData,
        nodes.Name,
        nodes.Getattr,
        nodes.Getitem,
        nodes.Const,
        nodes.Filter,
        nodes.Keyword,
    )
    if any(not isinstance(node, allowed) for node in tree.find_all(nodes.Node)):
        raise ValueError("Only variable interpolation and basic text filters are allowed")
    result = env.from_string(template).render(notification=event)
    if len(result) > 100000:
        raise ValueError("Rendered template too long")
    return result
