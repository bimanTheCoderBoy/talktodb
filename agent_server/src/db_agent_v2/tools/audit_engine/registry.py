from typing import Dict, List, Type, Tuple
from .base import BaseAuditFunction, EntityType, AuditCategory


class AuditFunctionRegistry:
    """Registry for audit functions by entity type and category"""
    
    def __init__(self):
        # Key: (entity_type, category) -> List of function classes
        self._functions: Dict[Tuple[EntityType, AuditCategory], List[Type[BaseAuditFunction]]] = {}
    
    def register(self, func_class: Type[BaseAuditFunction]) -> Type[BaseAuditFunction]:
        """Decorator to register an audit function"""
        for entity_type in func_class.entity_types:
            for category in func_class.categories:
                key = (entity_type, category)
                if key not in self._functions:
                    self._functions[key] = []
                self._functions[key].append(func_class)
        return func_class
    
    def get_functions(self, entity_type: EntityType, category: AuditCategory) -> List[Type[BaseAuditFunction]]:
        """Get all functions registered for an entity type and category"""
        # Get exact match
        exact_match = self._functions.get((entity_type, category), [])
        return exact_match
    
    def get_all_functions_for_entity(self, entity_type: EntityType) -> List[Type[BaseAuditFunction]]:
        """Get all functions for an entity type (any category)"""
        functions = []
        for (etype, _), funcs in self._functions.items():
            if etype == entity_type:
                functions.extend(funcs)
        return list(set(functions))  # deduplicate

    def iter_registered(self):
        """Iterate over all registered (entity_type, category) -> functions mappings."""
        return self._functions.items()


# Global registry
audit_function_registry = AuditFunctionRegistry()

