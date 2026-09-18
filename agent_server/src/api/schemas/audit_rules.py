from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


EntityTypeLiteral = Literal["cell", "site"]
RuleTypeLiteral = Literal[
    "not_null",
    "in_range",
    "gt",
    "lt",
    "gte",
    "lte",
    "eq",
    "neq",
    "boolean_true",
    "boolean_false",
    "regex",
]


class RuleTypeOption(BaseModel):
    value: RuleTypeLiteral
    label: str
    description: str
    requires_params: List[str] = Field(default_factory=list)


class TableColumnOption(BaseModel):
    name: str
    label: str
    data_type: str
    allowed_rule_types: List[RuleTypeLiteral] = Field(default_factory=list)


class TableCatalogEntry(BaseModel):
    table_name: str
    label: str
    entity_types: List[EntityTypeLiteral]
    columns: List[TableColumnOption]


class BuiltinRuleInfo(BaseModel):
    rule_key: str
    name: str
    description: str
    entity_types: List[str]
    categories: List[str]
    is_custom: bool = False
    is_enabled: bool = True
    custom_rule_id: Optional[int] = None
    is_customizable: bool = False
    defaults: Optional[Dict[str, Any]] = None
    user_config: Optional[Dict[str, Any]] = None
    config_schema: Optional[Dict[str, Any]] = None


class BuiltinRuleConfigUpdate(BaseModel):
    project_name: str
    config: Dict[str, Any] = Field(default_factory=dict)


class BuiltinRuleConfigResponse(BaseModel):
    rule_key: str
    project_name: str
    defaults: Dict[str, Any]
    user_config: Dict[str, Any]
    merged_config: Dict[str, Any]
    config_schema: Optional[Dict[str, Any]] = None


class AuditRulesCatalogResponse(BaseModel):
    rule_types: List[RuleTypeOption]
    tables: List[TableCatalogEntry]
    rule_types_by_data_type: Dict[str, List[str]] = Field(default_factory=dict)
    categories_note: str = "Custom rules apply only to Detailed (1-10 entities) and Moderate (11-50 entities) audit categories."


def _validate_check_rule_params(rule_type: str, rule_params: Dict[str, Any], column: str = "") -> None:
    """Validate rule_params for a single column check."""
    params = rule_params or {}
    prefix = f"Column '{column}': " if column else ""
    numeric_types = {"in_range", "gt", "lt", "gte", "lte"}
    value_types = {"eq", "neq"}

    if rule_type == "in_range":
        if "min" not in params or "max" not in params:
            raise ValueError(f"{prefix}in_range requires min and max parameters")
        try:
            min_val = float(params["min"])
            max_val = float(params["max"])
        except (TypeError, ValueError):
            raise ValueError(f"{prefix}min and max must be numeric")
        if min_val > max_val:
            raise ValueError(f"{prefix}min must be less than or equal to max")

    elif rule_type in numeric_types - {"in_range"}:
        if "value" not in params:
            raise ValueError(f"{prefix}{rule_type} requires a numeric value parameter")
        try:
            float(params["value"])
        except (TypeError, ValueError):
            raise ValueError(f"{prefix}value must be numeric")

    elif rule_type in value_types:
        if "value" not in params or params["value"] is None or str(params["value"]).strip() == "":
            raise ValueError(f"{prefix}{rule_type} requires a value parameter")

    elif rule_type == "regex":
        pattern = params.get("pattern", "")
        if not pattern or not str(pattern).strip():
            raise ValueError(f"{prefix}regex requires a pattern parameter")
        import re
        try:
            re.compile(str(pattern))
        except re.error as exc:
            raise ValueError(f"{prefix}Invalid regex pattern: {exc}")

    elif rule_type not in {"boolean_true", "boolean_false", "not_null"}:
        raise ValueError(f"{prefix}Unsupported rule type: {rule_type}")


class ColumnCheck(BaseModel):
    table_name: str
    column: str
    rule_type: RuleTypeLiteral
    rule_params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Table name is required")
        return cleaned

    @field_validator("column")
    @classmethod
    def validate_column(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Column name is required")
        return cleaned

    @model_validator(mode="after")
    def validate_params(self):
        _validate_check_rule_params(self.rule_type, self.rule_params, self.column)
        return self


class CustomAuditRuleCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    description: str = Field(default="", max_length=500)
    entity_type: EntityTypeLiteral
    table_name: Optional[str] = None
    column_checks: List[ColumnCheck] = Field(..., min_length=1, max_length=10)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Rule name is required")
        if len(cleaned) < 3:
            raise ValueError("Rule name must be at least 3 characters")
        return cleaned

    @model_validator(mode="after")
    def validate_checks(self):
        pairs = [(c.table_name, c.column) for c in self.column_checks]
        if len(set(pairs)) != len(pairs):
            raise ValueError("Each table/column pair can only have one check per rule")
        if not self.table_name:
            self.table_name = self.column_checks[0].table_name
        return self


class CustomAuditRuleUpdate(CustomAuditRuleCreate):
    pass


class CustomAuditRuleResponse(BaseModel):
    id: int
    email: str
    project_name: str
    name: str
    description: str
    entity_type: EntityTypeLiteral
    table_name: str
    column_checks: List[ColumnCheck]
    is_enabled: bool = True
    is_custom: bool = True
    rule_key: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuditRulesListResponse(BaseModel):
    builtin_rules: List[BuiltinRuleInfo]
    custom_rules: List[CustomAuditRuleResponse]
    preferences: Dict[str, bool]


class RulePreferenceUpdate(BaseModel):
    rule_key: str
    is_enabled: bool


class RulePreferencesBulkUpdate(BaseModel):
    project_name: str
    preferences: List[RulePreferenceUpdate] = Field(..., min_length=1)

    @field_validator("preferences")
    @classmethod
    def validate_preferences(cls, value: List[RulePreferenceUpdate]) -> List[RulePreferenceUpdate]:
        keys = [p.rule_key for p in value]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate rule keys in preferences update")
        return value


class BuiltinRuleConfigImportResponse(BaseModel):
    updated_rules: int
    rule_keys: List[str]
