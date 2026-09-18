from langchain_openai import ChatOpenAI
from agent.config.agent_config import CoverageLLMConfig
from agent.config.coverage_config import Coverage_IID_Executor_LLMConfig

# Create LLM instance using config
llm_config = CoverageLLMConfig()
llm = ChatOpenAI(**llm_config.model_dump())

coverage_iid_executor_llm=ChatOpenAI(**Coverage_IID_Executor_LLMConfig().model_dump())
