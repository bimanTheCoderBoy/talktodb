from langgraph.types import StreamWriter
from computer.schema.langgraph_event import LanggraphEvent
from computer.config.logger import get_computer_logger
from langgraph.config import get_stream_writer
logger = get_computer_logger(__name__)

def emit_langgraph_event(event: LanggraphEvent):
    stream_writer: StreamWriter = get_stream_writer()
    stream_writer(event.model_dump(mode="json"))
    logger.info(f"Event emitted: {event.model_dump(mode='json')}")