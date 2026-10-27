import logging
import os
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

load_dotenv()
logger = logging.getLogger(__name__)


# --------------------------------------------------
# CONFIGURACIÓN DE GEMINI
# --------------------------------------------------

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "25"))

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    temperature=0.1,
    timeout=GEMINI_TIMEOUT_SECONDS,
    max_retries=0,
)


# --------------------------------------------------
# ESTADO PERSISTENTE DEL AGENTE
# --------------------------------------------------

class AgentState(TypedDict, total=False):
    messages: list[str]
    response: str
    status: str
    approved: bool
    requires_approval: bool
    research_fallback_used: bool
    formatting_fallback_used: bool


# --------------------------------------------------
# UTILIDAD PARA NORMALIZAR RESPUESTAS
# --------------------------------------------------

def content_to_text(content: Any) -> str:
    """Convierte el contenido devuelto por Gemini en texto plano."""
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "\n".join(parts).strip()

    return str(content).strip()


# --------------------------------------------------
# NODO 1: INVESTIGACIÓN
# --------------------------------------------------

async def research_node(state: AgentState) -> dict:
    """Investiga el tema usando la llamada asíncrona al modelo."""
    prompt = str((state.get("messages") or [""])[-1]).strip()
    logger.info("[GRAPH] Iniciando investigación con Gemini")

    try:
        result = await llm.ainvoke(
            f"Resume en dos oraciones breves qué es: {prompt}"
        )
        response = content_to_text(result.content)
        if not response:
            raise ValueError("Gemini devolvió una respuesta vacía")

        logger.info("[GRAPH] Investigación completada")
        return {
            "response": response,
            "status": "investigando",
            "research_fallback_used": False,
        }

    except Exception:
        logger.exception("[GRAPH] Gemini falló durante la investigación")
        # Se identifica explícitamente como contingencia, no como respuesta de IA.
        fallback_response = (
            "No se pudo completar la investigación con Gemini. "
            "Se requiere revisar el resultado manualmente.\n\n"
            f"Tema solicitado: {prompt}"
        )
        return {
            "response": fallback_response,
            "status": "fallback_investigacion",
            "research_fallback_used": True,
        }


# --------------------------------------------------
# ENRUTAMIENTO CONDICIONAL SEGÚN requires_approval
# --------------------------------------------------

def route_after_research(state: AgentState) -> str:
    """Envía a aprobación humana solo si la tarea lo solicita."""
    if state.get("requires_approval", False) is True:
        return "human_approval"
    return "formatter"


# --------------------------------------------------
# NODO 2: APROBACIÓN HUMANA (HITL)
# --------------------------------------------------

def human_approval(state: AgentState) -> dict:
    logger.info("[GRAPH] Esperando decisión humana")

    # interrupt() pausa el grafo y permite persistir el checkpoint.
    decision = interrupt(
        {
            "type": "human_approval",
            "question": "¿Aprobás continuar con esta tarea?",
            "draft": state.get("response", ""),
            "research_fallback_used": state.get(
                "research_fallback_used", False
            ),
        }
    )

    # El worker reanuda con Command(resume={"approved": True/False}).
    approved = (
        isinstance(decision, dict)
        and isinstance(decision.get("approved"), bool)
        and decision["approved"] is True
    )

    logger.info(
        "[GRAPH] Decisión humana: %s",
        "APROBADA" if approved else "RECHAZADA",
    )
    return {
        "approved": approved,
        "status": "APPROVED" if approved else "REJECTED",
    }


# --------------------------------------------------
# NODO 3: FORMATEO
# --------------------------------------------------

async def formatting_node(state: AgentState) -> dict:
    """Da formato a la respuesta usando una llamada asíncrona a Gemini."""
    original_response = state.get("response", "")
    logger.info("[GRAPH] Formateando respuesta")

    try:
        result = await llm.ainvoke(
            "Dale formato profesional, claro y ordenado al siguiente texto. "
            "Conservá sus datos y no inventes información:\n\n"
            f"{original_response}"
        )
        response = content_to_text(result.content)
        if not response:
            raise ValueError("Gemini devolvió un texto vacío")

        return {
            "response": response,
            "status": "completado",
            "formatting_fallback_used": False,
        }

    except Exception:
        logger.exception("[GRAPH] Falló el formateo con Gemini")
        # Si falla el segundo llamado, conservamos el borrador original.
        return {
            "response": original_response,
            "status": "completado_con_fallback",
            "formatting_fallback_used": True,
        }


# --------------------------------------------------
# NODO DE RECHAZO
# --------------------------------------------------

def rejected_node(state: AgentState) -> dict:
    logger.info("[GRAPH] La persona rechazó la tarea")
    return {
        "status": "REJECTED",
        "approved": False,
    }


# --------------------------------------------------
# RAMIFICACIÓN DESPUÉS DE LA APROBACIÓN
# --------------------------------------------------

def route_after_approval(state: AgentState) -> str:
    if state.get("approved") is True:
        return "formatter"
    return "rejected"


# --------------------------------------------------
# CONSTRUCCIÓN DEL GRAFO
# --------------------------------------------------

def get_compiled_graph(checkpointer):
    workflow = StateGraph(AgentState)

    workflow.add_node("research", research_node)
    workflow.add_node("human_approval", human_approval)
    workflow.add_node("formatter", formatting_node)
    workflow.add_node("rejected", rejected_node)

    workflow.set_entry_point("research")

    # Esta rama evita interrumpir tareas que no requieren aprobación.
    workflow.add_conditional_edges(
        "research",
        route_after_research,
        {
            "human_approval": "human_approval",
            "formatter": "formatter",
        },
    )

    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "formatter": "formatter",
            "rejected": "rejected",
        },
    )

    workflow.add_edge("formatter", END)
    workflow.add_edge("rejected", END)

    # La pausa está dentro de human_approval mediante interrupt().
    return workflow.compile(checkpointer=checkpointer)
