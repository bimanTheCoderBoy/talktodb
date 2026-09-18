from pydantic import BaseModel
from sqlalchemy import Column, Integer, PrimaryKeyConstraint, String, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import ARRAY, Float, String, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

Base = declarative_base()

# the table is used to store the user project config and it will be strored in the User Db  not any db like we used in project name
class UserProjectConfig(Base):
    __tablename__ = "user_project_config"
    __table_args__ = (PrimaryKeyConstraint('email', 'project_name'),)
    email = Column(String, nullable=False)
    project_name = Column(String, nullable=False)
    cords=Column(ARRAY(Float, dimensions=2), default=list)
    cell_iids=Column(ARRAY(String), default=list)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)
    def __repr__(self):
        return f"<UserProjectConfig(email='{self.email}', project_name='{self.project_name}', cords='{self.cords}', cell_iids='{self.cell_iids}')>"


class UserAuditCustomRule(Base):
    """User-defined audit rules stored in the user database."""
    __tablename__ = "user_audit_custom_rule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, index=True)
    project_name = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    entity_type = Column(String, nullable=False)  # cell | site
    table_name = Column(String, nullable=False)
    columns = Column(ARRAY(String), nullable=False)
    rule_type = Column(String, nullable=False)
    rule_params = Column(JSONB, default=dict)
    column_checks = Column(JSONB, default=list)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<UserAuditCustomRule(id={self.id}, name='{self.name}', email='{self.email}')>"


class UserAuditRulePreference(Base):
    """Per-user enable/disable preferences for built-in and custom audit rules."""
    __tablename__ = "user_audit_rule_preference"
    __table_args__ = (PrimaryKeyConstraint("email", "project_name", "rule_key"),)

    email = Column(String, nullable=False)
    project_name = Column(String, nullable=False)
    rule_key = Column(String, nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<UserAuditRulePreference(rule_key='{self.rule_key}', is_enabled={self.is_enabled})>"


class UserAuditBuiltinRuleConfig(Base):
    """Per-user configuration overrides for customizable built-in audit rules."""
    __tablename__ = "user_audit_builtin_rule_config"
    __table_args__ = (PrimaryKeyConstraint("email", "project_name", "rule_key"),)

    email = Column(String, nullable=False)
    project_name = Column(String, nullable=False)
    rule_key = Column(String, nullable=False)
    config = Column(JSONB, default=dict)
    updated_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<UserAuditBuiltinRuleConfig(rule_key='{self.rule_key}', email='{self.email}')>" 