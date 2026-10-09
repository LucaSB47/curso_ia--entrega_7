import os
from dotenv import load_dotenv

# Carga las variables desde el archivo .env de forma segura
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

# IMPORTANTE: Importamos las versiones asíncronas para el checkpointer
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
import redis.asyncio as aioredis
from typing import TypedDict

class AgentState(TypedDict):
    messages: list[str]
    response: str

llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0.3)

async def call_model(state: AgentState):
    messages = state["messages"]
    prompt = messages[-1] if messages else "Hola"
    res = await llm.ainvoke(prompt)
    return {"response": res.content}

def human_approval(state: AgentState):
    interrupt("Se requiere aprobación humana para esta tarea crítica.")
    return state

# Creamos una única conexión global asíncrona para LangGraph 
# (Nota: no usamos decode_responses=True porque el checkpointer necesita manejar bytes puros)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
# Pasamos la URL directamente al checkpointer, LangGraph se encarga del resto
checkpointer = AsyncRedisSaver(redis_url=REDIS_URL)

def get_compiled_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("human_approval", human_approval)
    workflow.add_node("agent", call_model)
    
    workflow.set_entry_point("human_approval")
    workflow.add_edge("human_approval", "agent")
    workflow.add_edge("agent", END)
    
    # Compilamos el grafo inyectando el checkpointer asíncrono
    return workflow.compile(checkpointer=checkpointer)