from langchain_openai import ChatOpenAI
from computer.config.openrouter import ComputerLLMConfig

computer_llm = ChatOpenAI(
    api_key=ComputerLLMConfig().api_key,
    base_url=ComputerLLMConfig().base_url,
    model=ComputerLLMConfig().model,
    temperature=ComputerLLMConfig().temperature,
    extra_body=ComputerLLMConfig().model_dump().get("extra_body", {}),
)