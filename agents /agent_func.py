from langchain.agents import (
    AgentExecutor,
    create_openai_tools_agent,
)
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver


def create_agent(llm, tools: list, system_prompt):

    agent = create_openai_tools_agent(llm, tools, system_prompt)
    executor = AgentExecutor(agent=agent, tools=tools)

    return executor

def agent_node(state, agent, name):
    result = agent.invoke(state)
    message_content = result["output"]
    # Create a new message with the agent's name
    new_message = HumanMessage(content=message_content, name=name)
    # Return in the expected format
    return {"messages": [new_message]}
    # return node
# def agent_node(agent, name):
#     def node(state):
#         result = agent.invoke(state)
#         # Ensure we're returning the agent's response, not the input
#         return {"messages": result["output"] if "output" in result else result}
#     return node