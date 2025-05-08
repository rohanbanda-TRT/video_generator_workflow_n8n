from typing import List, Optional, Any
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain.memory import ConversationBufferMemory

def create_agent(
    llm: BaseChatModel,
    tools: List[BaseTool],
    system_prompt: ChatPromptTemplate,
    memory: Optional[Any] = None
) -> AgentExecutor:
    """
    Create an agent executor with the specified LLM, tools, and prompt.
    
    Args:
        llm: The language model to use
        tools: List of tools available to the agent
        system_prompt: The system prompt template
        memory: Optional memory for the agent
        
    Returns:
        An agent executor
    """
    # Create the agent
    agent = create_openai_functions_agent(
        llm=llm,
        tools=tools,
        prompt=system_prompt
    )
    
    # Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,
        early_stopping_method="generate"
    )
    
    return agent_executor
