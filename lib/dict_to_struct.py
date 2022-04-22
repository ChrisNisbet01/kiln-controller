from typing import Any


class Struct(object):
    def __init__(self, data: dict):
        for name, value in data.items():
            setattr(self, name, self._wrap(value))

    def _wrap(self, value: Any) -> "Struct":
        if isinstance(value, (tuple, list, set, frozenset)):
            return type(value)([self._wrap(v) for v in value])
        else:
            return Struct(value) if isinstance(value, dict) else value
