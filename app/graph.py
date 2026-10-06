import os
from dotenv import load_dotenv

# Carga las variables desde el archivo .env de forma segura
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from typing import TypedDict

class AgentState(TypedDict):
    messages: list[str]
    response: str

# Modelo configurado con la versión correcta
llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0.3)

async def call_model(state: AgentState):
    messages = state["messages"]
    prompt = messages[-1] if messages else "Hola"
    res = await llm.ainvoke(prompt)
    return {"response": res.content}

def get_compiled_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.set_entry_point("agent")
    workflow.add_edge("agent", END)
    return workflow.compile()