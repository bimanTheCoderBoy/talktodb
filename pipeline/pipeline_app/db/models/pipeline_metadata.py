from sqlalchemy import Column, Integer, Text, DateTime, func
from pipeline_app.db.models._base import Base

class PipelineMetadata(Base):
    __tablename__ = "pipeline_metadata"

    # PK
    id = Column(Integer, primary_key=True, autoincrement=True)

    project_name = Column(Text)
    entity_type = Column(Text)
    run_type = Column(Text)
    status = Column(Text)
    total_records = Column(Integer)
    records_processed = Column(Integer)
    error_message = Column(Text)
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)