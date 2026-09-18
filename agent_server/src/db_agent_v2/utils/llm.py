from langchain_openai import ChatOpenAI
from db_agent_v2.config.agent_config import ExecutorLLMConfig
from db_agent_v2.config.agent_config import SummaryLLMConfig

# Orchestrator LLM Configuration (OpenRouter)
executor_llm = ChatOpenAI(**ExecutorLLMConfig().model_dump())

summary_llm = ChatOpenAI(**SummaryLLMConfig().model_dump())
