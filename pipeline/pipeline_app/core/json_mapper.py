"""
Generic JSON-to-Pydantic mapper for EDS API records.

Replaces both the extraction helpers in schemas.py and the entire
payload_loader.py with a single reusable class that caches field-path
introspection and supports optional context injection.

Public API:
    extract_value  -- dot-path + array-index walker (standalone)
    JsonMapper     -- generic, reusable record-to-model mapper
"""

from typing import Any, Dict, Generic, List, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def extract_value(data: dict, path: str) -> Any:
    """Navigate a nested dict using a dot-separated path.

    Supports:
      - Dot paths:      ``"security.createDate"``
      - Special keys:   ``"$type"``
      - Array indexing:  ``"lte.carriers[0].iid"``
      - Lists as intermediates: auto-selects first element

    Returns *None* when any intermediate key is missing or the
    structure doesn't match the expected shape.
    """
    keys = path.split(".")
    current = data

    for key in keys:
        if current is None:
            return None

        if "[" in key and "]" in key:
            name, idx_str = key[:-1].split("[")
            current = current.get(name, [])
            idx = int(idx_str)
            if not isinstance(current, list) or idx >= len(current):
                return None
            current = current[idx]
        else:
            if isinstance(current, list):
                current = current[0] if current else None
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None

    return current


class JsonMapper(Generic[T]):
    """Maps raw EDS API JSON records to Pydantic model instances.

    Introspects the model's ``json_schema_extra["json_path"]`` metadata
    once at construction and caches the field-to-path mapping for reuse
    across thousands of records.

    Parameters
    ----------
    model_class : Type[T]
        A Pydantic model class whose fields carry ``json_path`` metadata.
    """

    __slots__ = ("_model_class", "_field_paths")

    def __init__(self, model_class: Type[T]) -> None:
        self._model_class = model_class
        field_paths: Dict[str, str] = {}

        for name, info in model_class.model_fields.items():
            extra = info.json_schema_extra
            if extra and "json_path" in extra:
                field_paths[name] = extra["json_path"]

        self._field_paths: Dict[str, str] = field_paths

    @property
    def model_class(self) -> Type[T]:
        return self._model_class

    def map(self, record: dict, **context: Any) -> T:
        """Map a single raw API dict to a validated Pydantic model.

        Parameters
        ----------
        record : dict
            Raw JSON record from the EDS API.
        **context
            Optional field overrides merged *after* extraction,
            e.g. ``mu_iid="MU-1"`` for antenna context injection.
            Unknown field names raise ``ValueError``.
        """
        values: Dict[str, Any] = {
            name: extract_value(record, path)
            for name, path in self._field_paths.items()
        }

        if context:
            unknown = context.keys() - self._field_paths.keys()
            if unknown:
                raise ValueError(
                    f"{self!r}: unknown fields in context: {unknown}"
                )
            values.update(context)

        return self._model_class(**values)

    def map_batch(self, records: List[dict], **context: Any) -> List[T]:
        """Map a list of raw API dicts to a list of Pydantic models.

        Shared ``**context`` is applied to every record.
        """
        return [self.map(r, **context) for r in records]

    def __repr__(self) -> str:
        return f"JsonMapper({self._model_class.__name__})"
