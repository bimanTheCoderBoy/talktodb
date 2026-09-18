from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Any, Dict
from enum import Enum
from db_agent_v2.config.tool_config import AuditCategory

class EntityType(str, Enum):
    CELL = "cell"
    SITE = "site"


@dataclass
class AuditFunctionResult:
    """Standard return format for all audit functions"""
    summary: str              # One line summary in markdown
    md_data: str              # Detailed markdown data
    error: Optional[str] = None
    success: bool = True
    raw_data: Optional[List[dict]] = None  # Raw query results for downstream processing
    stats: Optional[dict] = None           # Statistics if applicable
    
    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "md_data": self.md_data,
            "error": self.error,
            "success": self.success,
            "raw_data": self.raw_data,
            "stats": self.stats
        }


class BaseAuditFunction(ABC):
    """Base class for all audit functions"""
    
    # Metadata for registration
    name: str = ""
    description: str = ""
    entity_types: List[EntityType] = []  # Which entities this function supports
    categories: List[AuditCategory] = [] # Which categories this function runs in
    
    def __init__(self, db_manager, rule_config: Optional[Dict[str, Any]] = None):
        self.db_manager = db_manager
        self._rule_config = rule_config

    def get_config(self) -> Dict[str, Any]:
        """Return merged built-in defaults + user overrides for customizable rules."""
        from .builtin_rule_catalog import CUSTOMIZABLE_BUILTIN_RULE_KEYS, merge_rule_config

        if self.name in CUSTOMIZABLE_BUILTIN_RULE_KEYS:
            return merge_rule_config(self.name, self._rule_config)
        return self._rule_config or {}
    
    @abstractmethod
    async def execute(self, project_name: str, entity_names: List[str], user_email: str) -> AuditFunctionResult:
        """Execute the audit function"""
        pass
    
    async def _fetch_query(self, project_name: str, query: str, user_email: str, params=None) -> List[dict]:
        """Helper to execute queries"""
        result = await self.db_manager.execute_query(project_name, query, user_email, params)
        if not result['status']:
            raise Exception(f"Query error: {result['error']}")
        return result['data']

