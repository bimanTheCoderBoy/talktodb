from sqlalchemy.orm import declarative_base, declared_attr
from sqlalchemy import Column, Text, DateTime, func

Base = declarative_base()

class ImportedAtMixin:
    """Adds an imported_at column to the model."""
    imported_at = Column(DateTime, default=func.now())

class SecurityColumnsMixin:
    """EDS security/audit columns -- identical across Location, MuLTE, MuNR, CellLTE, CellNR."""
    security_createdate = Column(DateTime)
    security_modifydate = Column(DateTime)
    security_createuser = Column(Text)
    security_modifyuser = Column(Text)
    security_usergroup = Column(Text)
    security_visibilityinfo_usergroup = Column(Text)
    security_visibilityinfo_visibility_owner = Column(Text)
    security_visibilityinfo_visibility_group = Column(Text)
    security_visibilityinfo_visibility_all = Column(Text)
    security_permissions_owner = Column(Text)
    security_permissions_group = Column(Text)
    security_permissions_all = Column(Text)