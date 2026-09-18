from sqlalchemy import Column, Integer, Text, DateTime, Index, func
from pipeline_app.db.models._base import Base

class Discrepancy(Base):
    __tablename__ = "discrepancies"
    __table_args__ = (
        Index("ix_discrepancies_imported_at", "imported_at"),
    )

    # PK
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Reference columns
    cell_name = Column(Text, index=True)
    enodeb_name = Column(Text, index=True)
    column_name = Column(Text) # maps to 'column' in CSV
    oss_value = Column(Text)
    db_value = Column(Text)    # maps to 'db_value' in CSV
    location_eid = Column(Text, index=True)
    cell_eid = Column(Text, index=True)
    technology = Column(Text)
    status = Column(Text)
    checked_at = Column(Text)  # timestamp string from CSV

    # Meta
    imported_at = Column(DateTime, default=func.now())