from typing import Dict, Callable, Any
from db_agent_v2.config.tool_config import DBconfig
from db_agent_v2.db.DatabaseManager import init_db_manager

class ToolRegistry:
    """Central registry for managing tools"""

    def __init__(self):
        self._tools: Dict[str, Callable[..., Any]] = {}
        self._factories: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, tool: Callable[..., Any]) -> None:
        """Register a tool instance directly. [not using now in the project]"""
        self._tools[name] = tool

    def register_factory(self, name: str, factory: Callable[..., Any]) -> None:
        """Register a tool factory function. [use it to register]"""
        self._factories[name] = factory

    def get_tool(self, name: str,) -> Callable[..., Any]:
        """
        Get a tool by name, creating it via its factory if needed.
        Factories are called with no arguments.
        """
        if name in self._tools:
            return self._tools[name]

        if name in self._factories:
           
            tool = self._factories[name]()
            if tool is None:
                raise ValueError(f"Tool '{name}' factory returned None")

            self._tools[name] = tool
            return tool

        raise ValueError(f"Tool '{name}' not found")

    def get_all_tools(self) -> list[Callable[..., Any]]:
        """Get all registered tools, instantiating any factories as needed."""
        tools = []
        for name in set(self._tools.keys()) | set(self._factories.keys()):
            tools.append(self.get_tool(name))
        return tools



#connect to the database
db_config = DBconfig()
init_db_manager(db_config.host, db_config.port, db_config.user, db_config.password, db_config.min_size, db_config.max_size)

# Global registry
tool_registry = ToolRegistry()

# Register tools from tools package
from db_agent_v2.tools.asset_db_rag.tool import create_asset_db_rag_tool
from db_agent_v2.tools.ask_human.tool import create_ask_user_tool
from db_agent_v2.tools.discrepancy_engine.tool import create_discrepancy_engine_tool

tool_registry.register_factory("asset_db_rag_tool", create_asset_db_rag_tool)
# tool_registry.register_factory("ask_user_tool", create_ask_user_tool)
tool_registry.register_factory("discrepancy_engine_tool", create_discrepancy_engine_tool)

from db_agent_v2.tools.eds_fixer.tool import create_eds_fixer_tool
tool_registry.register_factory("run_eds_fixer_tool", create_eds_fixer_tool)

from db_agent_v2.tools.audit_engine.tool import create_audit_engine_tool
tool_registry.register_factory("audit_engine_tool", create_audit_engine_tool)

from db_agent_v2.tools.update_eds.tool import create_update_eds_tool
tool_registry.register_factory("update_eds_tool", create_update_eds_tool)

from db_agent_v2.tools.doc_retrieval.tool import create_doc_retrieval_tool
tool_registry.register_factory("doc_retrieval_tool", create_doc_retrieval_tool)