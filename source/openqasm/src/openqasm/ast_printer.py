from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass


def pretty_print(obj, indent=4):
    """
    Pretty prints a (possibly deeply-nested) dataclass.
    Each new block will be indented by `indent` spaces (default is 4).
    """
    print(stringify(obj, indent))


def stringify(obj, indent=4, _indents=0):
    if isinstance(obj, str):
        return f"'{obj}'"

    if not is_dataclass(obj) and not isinstance(obj, (Mapping, Iterable)):
        return str(obj)

    this_indent = indent * _indents * " "
    next_indent = indent * (_indents + 1) * " "
    start, end = f"{type(obj).__name__}(", ")"  # dicts, lists, and tuples will re-assign this

    if is_dataclass(obj):
        body = "\n".join(
            f"{next_indent}{field.name}="
            f"{stringify(getattr(obj, field.name), indent, _indents + 1)},"
            for field in fields(obj)
        )

    elif isinstance(obj, Mapping):
        if isinstance(obj, dict):
            start, end = "{}"

        body = "\n".join(
            f"{next_indent}{stringify(key, indent, _indents + 1)}: "
            f"{stringify(value, indent, _indents + 1)},"
            for key, value in obj.items()
        )

    elif isinstance(obj, Iterable):
        if isinstance(obj, list):
            start, end = "[]"
        elif isinstance(obj, tuple):
            start, end = "()"

        body = "\n".join(f"{next_indent}{stringify(item, indent, _indents + 1)}," for item in obj)
    else:
        body = obj.__repr__()

    return f"{start}\n{body}\n{this_indent}{end}"
