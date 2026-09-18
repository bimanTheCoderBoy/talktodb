"""Load user audit rule preferences from the user database."""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from api.db.database import user_db_session
from api.db.models import UserAuditBuiltinRuleConfig, UserAuditCustomRule, UserAuditRulePreference
from db_agent_v2.config.tool_config import AuditCategory
from .catalog import custom_rule_key

logger = logging.getLogger(__name__)

CUSTOM_RULE_CATEGORIES = {AuditCategory.DETAILED, AuditCategory.MODERATE}


async def load_rule_preferences(email: str, project_name: str) -> Dict[str, bool]:
    """Return rule_key -> is_enabled map. Missing keys default to enabled."""
    async with user_db_session() as session:
        result = await session.execute(
            select(UserAuditRulePreference).where(
                UserAuditRulePreference.email == email,
                UserAuditRulePreference.project_name == project_name,
            )
        )
        rows = result.scalars().all()
        return {row.rule_key: row.is_enabled for row in rows}


async def load_builtin_rule_configs(email: str, project_name: str) -> Dict[str, Dict[str, Any]]:
    """Return rule_key -> user override config (not merged with defaults)."""
    async with user_db_session() as session:
        result = await session.execute(
            select(UserAuditBuiltinRuleConfig).where(
                UserAuditBuiltinRuleConfig.email == email,
                UserAuditBuiltinRuleConfig.project_name == project_name,
            )
        )
        rows = result.scalars().all()

    return {row.rule_key: row.config or {} for row in rows}


def is_rule_enabled(rule_key: str, preferences: Dict[str, bool]) -> bool:
    """Built-in and custom rules default to enabled when no preference exists."""
    if rule_key not in preferences:
        return True
    return preferences[rule_key]


async def load_enabled_custom_rules(
    email: str,
    project_name: str,
    entity_type: str,
    category: AuditCategory,
    preferences: Optional[Dict[str, bool]] = None,
) -> List[UserAuditCustomRule]:
    """Load custom rules for the user that are enabled and applicable to the category."""
    if category not in CUSTOM_RULE_CATEGORIES:
        return []

    prefs = preferences if preferences is not None else await load_rule_preferences(email, project_name)

    async with user_db_session() as session:
        result = await session.execute(
            select(UserAuditCustomRule).where(
                UserAuditCustomRule.email == email,
                UserAuditCustomRule.project_name == project_name,
                UserAuditCustomRule.entity_type == entity_type,
            ).order_by(UserAuditCustomRule.id)
        )
        rules = result.scalars().all()

    enabled_rules = []
    for rule in rules:
        key = custom_rule_key(rule.id)
        if is_rule_enabled(key, prefs):
            enabled_rules.append(rule)
    return enabled_rules
