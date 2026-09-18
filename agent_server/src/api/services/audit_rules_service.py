import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import UserAuditBuiltinRuleConfig, UserAuditCustomRule, UserAuditRulePreference
from api.schemas.audit_rules import (
    AuditRulesCatalogResponse,
    AuditRulesListResponse,
    BuiltinRuleConfigImportResponse,
    BuiltinRuleConfigResponse,
    BuiltinRuleConfigUpdate,
    BuiltinRuleInfo,
    ColumnCheck,
    CustomAuditRuleCreate,
    CustomAuditRuleResponse,
    CustomAuditRuleUpdate,
    RulePreferencesBulkUpdate,
    RuleTypeOption,
    TableCatalogEntry,
    TableColumnOption,
)
from db_agent_v2.tools.audit_engine.custom_rules import normalize_column_checks
from db_agent_v2.tools.audit_engine.catalog import (
    AUDIT_TABLE_CATALOG,
    RULE_TYPE_OPTIONS,
    RULE_TYPES_BY_DATA_TYPE,
    allowed_rule_types_for_column,
    custom_rule_key,
    validate_custom_rule_payload,
)
from db_agent_v2.tools.audit_engine.registry import audit_function_registry
from db_agent_v2.tools.audit_engine.builtin_rule_catalog import (
    BUILTIN_RULE_DEFAULTS,
    CUSTOMIZABLE_BUILTIN_RULE_KEYS,
    get_customizable_rule_schema,
    merge_rule_config,
)
from db_agent_v2.tools.audit_engine.builtin_rule_config_csv import (
    build_export_csv,
    parse_import_csv,
    rule_display_name,
)
# Ensure built-in audit functions are registered before listing rules
from db_agent_v2.tools.audit_engine.functions import cell_functions, cell_nr_functions, site_functions  # noqa: F401

logger = logging.getLogger(__name__)


class AuditRulesService:
    @staticmethod
    def _column_checks_for_row(row) -> List[ColumnCheck]:
        checks = normalize_column_checks(row)
        return [ColumnCheck(**check) for check in checks]

    @staticmethod
    def _serialize_column_checks(column_checks: List[ColumnCheck]) -> List[dict]:
        return [check.model_dump() for check in column_checks]

    @staticmethod
    def _custom_rule_response(row, is_enabled: bool) -> CustomAuditRuleResponse:
        column_checks = AuditRulesService._column_checks_for_row(row)
        return CustomAuditRuleResponse(
            id=row.id,
            email=row.email,
            project_name=row.project_name,
            name=row.name,
            description=row.description or "",
            entity_type=row.entity_type,
            table_name=row.table_name,
            column_checks=column_checks,
            is_enabled=is_enabled,
            is_custom=True,
            rule_key=custom_rule_key(row.id),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def get_catalog() -> AuditRulesCatalogResponse:
        tables = []
        for t in AUDIT_TABLE_CATALOG:
            columns = [
                TableColumnOption(
                    name=c["name"],
                    label=c["label"],
                    data_type=c["data_type"],
                    allowed_rule_types=allowed_rule_types_for_column(t["table_name"], c["name"]),
                )
                for c in t["columns"]
            ]
            tables.append(
                TableCatalogEntry(
                    table_name=t["table_name"],
                    label=t["label"],
                    entity_types=t["entity_types"],
                    columns=columns,
                )
            )
        return AuditRulesCatalogResponse(
            rule_types=[RuleTypeOption(**opt) for opt in RULE_TYPE_OPTIONS],
            rule_types_by_data_type=RULE_TYPES_BY_DATA_TYPE,
            tables=tables,
        )

    @staticmethod
    async def _get_builtin_config_map(
        db: AsyncSession,
        email: str,
        project_name: str,
    ) -> Dict[str, Dict]:
        result = await db.execute(
            select(UserAuditBuiltinRuleConfig).where(
                UserAuditBuiltinRuleConfig.email == email,
                UserAuditBuiltinRuleConfig.project_name == project_name,
            )
        )
        return {row.rule_key: row.config or {} for row in result.scalars().all()}

    @staticmethod
    def _collect_builtin_rules(
        preferences: Dict[str, bool],
        user_configs: Optional[Dict[str, Dict]] = None,
    ) -> List[BuiltinRuleInfo]:
        user_configs = user_configs or {}
        seen = set()
        rules: List[BuiltinRuleInfo] = []

        for (entity_type, category), func_classes in audit_function_registry.iter_registered():
            for func_class in func_classes:
                if func_class.name in seen:
                    continue
                seen.add(func_class.name)
                is_customizable = func_class.name in CUSTOMIZABLE_BUILTIN_RULE_KEYS
                defaults = BUILTIN_RULE_DEFAULTS.get(func_class.name) if is_customizable else None
                overrides = user_configs.get(func_class.name)
                merged = merge_rule_config(func_class.name, overrides) if is_customizable else None
                rules.append(
                    BuiltinRuleInfo(
                        rule_key=func_class.name,
                        name=rule_display_name(func_class.name),
                        description=func_class.description,
                        entity_types=[et.value for et in func_class.entity_types],
                        categories=[cat.value for cat in func_class.categories],
                        is_custom=False,
                        is_enabled=preferences.get(func_class.name, True),
                        is_customizable=is_customizable,
                        defaults=defaults,
                        user_config=overrides or {},
                        config_schema=get_customizable_rule_schema(func_class.name) if is_customizable else None,
                    )
                )
                if merged and rules[-1].user_config is not None:
                    rules[-1].user_config = overrides or {}

        rules.sort(key=lambda r: r.name.lower())
        return rules

    @staticmethod
    async def _get_preferences_map(
        db: AsyncSession,
        email: str,
        project_name: str,
    ) -> Dict[str, bool]:
        result = await db.execute(
            select(UserAuditRulePreference).where(
                UserAuditRulePreference.email == email,
                UserAuditRulePreference.project_name == project_name,
            )
        )
        return {row.rule_key: row.is_enabled for row in result.scalars().all()}

    @staticmethod
    async def list_rules(
        db: AsyncSession,
        email: str,
        project_name: str,
    ) -> AuditRulesListResponse:
        preferences = await AuditRulesService._get_preferences_map(db, email, project_name)
        user_configs = await AuditRulesService._get_builtin_config_map(db, email, project_name)

        result = await db.execute(
            select(UserAuditCustomRule).where(
                UserAuditCustomRule.email == email,
                UserAuditCustomRule.project_name == project_name,
            ).order_by(UserAuditCustomRule.id)
        )
        custom_rows = result.scalars().all()

        custom_rules = [
            AuditRulesService._custom_rule_response(row, preferences.get(custom_rule_key(row.id), True))
            for row in custom_rows
        ]

        return AuditRulesListResponse(
            builtin_rules=AuditRulesService._collect_builtin_rules(preferences, user_configs),
            custom_rules=custom_rules,
            preferences=preferences,
        )

    @staticmethod
    def _builtin_rule_name_map() -> Dict[str, str]:
        seen = set()
        names: Dict[str, str] = {}
        for _, func_classes in audit_function_registry.iter_registered():
            for func_class in func_classes:
                if func_class.name in seen:
                    continue
                seen.add(func_class.name)
                if func_class.name in CUSTOMIZABLE_BUILTIN_RULE_KEYS:
                    names[func_class.name] = rule_display_name(func_class.name)
        for rule_key in CUSTOMIZABLE_BUILTIN_RULE_KEYS:
            names.setdefault(rule_key, rule_display_name(rule_key))
        return names

    @staticmethod
    async def export_builtin_configs_csv(
        db: AsyncSession,
        email: str,
        project_name: str,
    ) -> str:
        user_configs = await AuditRulesService._get_builtin_config_map(db, email, project_name)
        return build_export_csv(user_configs, AuditRulesService._builtin_rule_name_map())

    @staticmethod
    async def import_builtin_configs_csv(
        db: AsyncSession,
        email: str,
        project_name: str,
        csv_content: str,
    ) -> BuiltinRuleConfigImportResponse:
        try:
            configs, errors = parse_import_csv(csv_content)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        if errors:
            raise HTTPException(status_code=422, detail={"errors": errors})

        updated_keys: List[str] = []
        for rule_key, config in configs.items():
            result = await db.execute(
                select(UserAuditBuiltinRuleConfig).where(
                    UserAuditBuiltinRuleConfig.email == email,
                    UserAuditBuiltinRuleConfig.project_name == project_name,
                    UserAuditBuiltinRuleConfig.rule_key == rule_key,
                )
            )
            row = result.scalar_one_or_none()
            if row:
                row.config = config
                row.updated_at = datetime.now()
            else:
                db.add(
                    UserAuditBuiltinRuleConfig(
                        email=email,
                        project_name=project_name,
                        rule_key=rule_key,
                        config=config,
                        updated_at=datetime.now(),
                    )
                )
            updated_keys.append(rule_key)

        await db.flush()
        return BuiltinRuleConfigImportResponse(
            updated_rules=len(updated_keys),
            rule_keys=sorted(updated_keys),
        )

    @staticmethod
    async def upsert_builtin_config(
        db: AsyncSession,
        email: str,
        rule_key: str,
        data: BuiltinRuleConfigUpdate,
    ) -> BuiltinRuleConfigResponse:
        if rule_key not in CUSTOMIZABLE_BUILTIN_RULE_KEYS:
            raise HTTPException(status_code=404, detail="Rule is not customizable")

        result = await db.execute(
            select(UserAuditBuiltinRuleConfig).where(
                UserAuditBuiltinRuleConfig.email == email,
                UserAuditBuiltinRuleConfig.project_name == data.project_name,
                UserAuditBuiltinRuleConfig.rule_key == rule_key,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.config = data.config or {}
            row.updated_at = datetime.now()
        else:
            row = UserAuditBuiltinRuleConfig(
                email=email,
                project_name=data.project_name,
                rule_key=rule_key,
                config=data.config or {},
                updated_at=datetime.now(),
            )
            db.add(row)

        await db.flush()
        merged = merge_rule_config(rule_key, row.config or {})
        return BuiltinRuleConfigResponse(
            rule_key=rule_key,
            project_name=data.project_name,
            defaults=BUILTIN_RULE_DEFAULTS[rule_key],
            user_config=row.config or {},
            merged_config=merged,
            config_schema=get_customizable_rule_schema(rule_key),
        )

    @staticmethod
    async def _assert_unique_custom_rule_name(
        db: AsyncSession,
        email: str,
        project_name: str,
        name: str,
        exclude_rule_id: Optional[int] = None,
    ) -> None:
        result = await db.execute(
            select(UserAuditCustomRule).where(
                UserAuditCustomRule.email == email,
                UserAuditCustomRule.project_name == project_name,
            )
        )
        normalized = name.strip().casefold()
        for row in result.scalars().all():
            if exclude_rule_id is not None and row.id == exclude_rule_id:
                continue
            if row.name.strip().casefold() == normalized:
                raise HTTPException(
                    status_code=422,
                    detail="A custom rule with this name already exists",
                )

    @staticmethod
    async def create_custom_rule(
        db: AsyncSession,
        email: str,
        project_name: str,
        data: CustomAuditRuleCreate,
    ) -> CustomAuditRuleResponse:
        column_checks = data.column_checks
        serialized_checks = AuditRulesService._serialize_column_checks(column_checks)
        try:
            validate_custom_rule_payload(data.entity_type, serialized_checks)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        await AuditRulesService._assert_unique_custom_rule_name(
            db, email, project_name, data.name.strip()
        )

        row = UserAuditCustomRule(
            email=email,
            project_name=project_name,
            name=data.name.strip(),
            description=(data.description or "").strip(),
            entity_type=data.entity_type,
            table_name=data.table_name or column_checks[0].table_name,
            columns=[c.column for c in column_checks],
            rule_type=column_checks[0].rule_type,
            rule_params=column_checks[0].rule_params,
            column_checks=serialized_checks,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)

        return AuditRulesService._custom_rule_response(row, is_enabled=True)

    @staticmethod
    async def update_custom_rule(
        db: AsyncSession,
        email: str,
        project_name: str,
        rule_id: int,
        data: CustomAuditRuleUpdate,
    ) -> CustomAuditRuleResponse:
        result = await db.execute(
            select(UserAuditCustomRule).where(
                UserAuditCustomRule.id == rule_id,
                UserAuditCustomRule.email == email,
                UserAuditCustomRule.project_name == project_name,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Custom rule not found")

        column_checks = data.column_checks
        serialized_checks = AuditRulesService._serialize_column_checks(column_checks)
        try:
            validate_custom_rule_payload(data.entity_type, serialized_checks)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        await AuditRulesService._assert_unique_custom_rule_name(
            db, email, project_name, data.name.strip(), exclude_rule_id=rule_id
        )

        row.name = data.name.strip()
        row.description = (data.description or "").strip()
        row.entity_type = data.entity_type
        row.table_name = data.table_name or column_checks[0].table_name
        row.columns = [c.column for c in column_checks]
        row.rule_type = column_checks[0].rule_type
        row.rule_params = column_checks[0].rule_params
        row.column_checks = serialized_checks
        row.updated_at = datetime.now()

        await db.flush()
        await db.refresh(row)

        preferences = await AuditRulesService._get_preferences_map(db, email, project_name)
        return AuditRulesService._custom_rule_response(
            row,
            is_enabled=preferences.get(custom_rule_key(row.id), True),
        )

    @staticmethod
    async def delete_custom_rule(
        db: AsyncSession,
        email: str,
        project_name: str,
        rule_id: int,
    ) -> None:
        result = await db.execute(
            select(UserAuditCustomRule).where(
                UserAuditCustomRule.id == rule_id,
                UserAuditCustomRule.email == email,
                UserAuditCustomRule.project_name == project_name,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Custom rule not found")

        key = custom_rule_key(rule_id)
        await db.execute(
            delete(UserAuditRulePreference).where(
                UserAuditRulePreference.email == email,
                UserAuditRulePreference.project_name == project_name,
                UserAuditRulePreference.rule_key == key,
            )
        )
        await db.delete(row)

    @staticmethod
    async def update_preferences(
        db: AsyncSession,
        email: str,
        data: RulePreferencesBulkUpdate,
    ) -> Dict[str, bool]:
        updated: Dict[str, bool] = {}

        for pref in data.preferences:
            result = await db.execute(
                select(UserAuditRulePreference).where(
                    UserAuditRulePreference.email == email,
                    UserAuditRulePreference.project_name == data.project_name,
                    UserAuditRulePreference.rule_key == pref.rule_key,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.is_enabled = pref.is_enabled
                existing.updated_at = datetime.now()
            else:
                db.add(
                    UserAuditRulePreference(
                        email=email,
                        project_name=data.project_name,
                        rule_key=pref.rule_key,
                        is_enabled=pref.is_enabled,
                        updated_at=datetime.now(),
                    )
                )
            updated[pref.rule_key] = pref.is_enabled

        return updated
