import asyncio
import json
import logging
import os

import redis.asyncio as aioredis
from dotenv import load_dotenv
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.types import Command

from app.graph import get_compiled_graph

load_dotenv()
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
GRAPH_TIMEOUT_SECONDS = float(os.getenv("GRAPH_TIMEOUT_SECONDS", "60"))

# Pool reutilizable para las operaciones de estado del worker.
redis_pool = aioredis.ConnectionPool.from_url(
    REDIS_URL,
    decode_responses=True,
)


def redis_bool(value: bool) -> str:
    return "true" if value else "false"


def serialize_interrupt(interrupt_obj) -> str:
    """Convierte los datos de una interrupción a JSON para almacenarlos en Redis."""
    payload = getattr(interrupt_obj, "value", interrupt_obj)
    return json.dumps(payload, ensure_ascii=False, default=str)


async def update_job(redis_client, job_id: str, **fields) -> None:
    """Actualiza los campos de un trabajo en Redis."""
    mapping = {
        key: str(value)
        for key, value in fields.items()
        if value is not None
    }
    if mapping:
        await redis_client.hset(f"job:{job_id}", mapping=mapping)


async def run_agent_task(job_id: str, task_data: dict) -> None:
    """Ejecuta un trabajo nuevo o reanuda uno pausado por HITL."""
    redis_client = aioredis.Redis(connection_pool=redis_pool)

    try:
        await redis_client.ping()
        is_resume = task_data.get("is_resume") is True

        # --------------------------------------------------
        # VALIDAR LOS DATOS DE ENTRADA
        # --------------------------------------------------
        if is_resume:
            approved = task_data.get("approved")
            if not isinstance(approved, bool):
                raise ValueError(
                    "Para reanudar la tarea, 'approved' debe ser un booleano."
                )
            logger.info(
                "[WORKER] Reanudando job=%s; approved=%s",
                job_id,
                approved,
            )
        else:
            prompt = task_data.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("La tarea necesita un prompt de texto no vacío.")

            requires_approval = task_data.get("requires_approval", False)
            if not isinstance(requires_approval, bool):
                raise ValueError("'requires_approval' debe ser un booleano.")

            logger.info(
                "[WORKER] Iniciando job=%s; requires_approval=%s",
                job_id,
                requires_approval,
            )

        await update_job(redis_client, job_id, status="RUNNING", error="")

        # --------------------------------------------------
        # CHECKPOINTER REDIS Y GRAFO
        # --------------------------------------------------
        async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
            await checkpointer.asetup()
            graph = get_compiled_graph(checkpointer)

            # El mismo thread_id permite recuperar el checkpoint al reanudar.
            config = {"configurable": {"thread_id": job_id}}

            # --------------------------------------------------
            # EJECUTAR O REANUDAR
            # --------------------------------------------------
            if is_resume:
                graph_input = Command(resume={"approved": approved})
            else:
                graph_input = {
                    "messages": [prompt.strip()],
                    "response": "",
                    "status": "starting",
                    "approved": False,
                    "requires_approval": requires_approval,
                    "research_fallback_used": False,
                    "formatting_fallback_used": False,
                }

            logger.info("[WORKER] Ejecutando grafo para job=%s", job_id)
            result = await asyncio.wait_for(
                graph.ainvoke(graph_input, config=config),
                timeout=GRAPH_TIMEOUT_SECONDS,
            )

            snapshot = await graph.aget_state(config)
            state_values = snapshot.values or {}

            # --------------------------------------------------
            # CASO 1: EL GRAFO ESPERA APROBACIÓN HUMANA
            # --------------------------------------------------
            interrupts = (
                result.get("__interrupt__", [])
                if isinstance(result, dict)
                else []
            )

            if interrupts:
                approval_payload = serialize_interrupt(interrupts[0])
                final_draft = state_values.get("response", "")

                await update_job(
                    redis_client,
                    job_id,
                    status="PAUSED_FOR_APPROVAL",
                    result=final_draft,
                    approval_payload=approval_payload,
                    result_status=state_values.get("status", "investigando"),
                    requires_approval="true",
                    research_fallback_used=redis_bool(
                        state_values.get("research_fallback_used", False)
                    ),
                    formatting_fallback_used="false",
                    error="",
                )
                logger.info(
                    "[WORKER] Job %s pausado para aprobación humana",
                    job_id,
                )
                return

            # --------------------------------------------------
            # CASO 2: RECHAZO HUMANO
            # --------------------------------------------------
            if state_values.get("status") == "REJECTED":
                await update_job(
                    redis_client,
                    job_id,
                    status="REJECTED",
                    result=state_values.get("response", ""),
                    result_status="REJECTED",
                    approved="false",
                    requires_approval="true",
                    research_fallback_used=redis_bool(
                        state_values.get("research_fallback_used", False)
                    ),
                    formatting_fallback_used="false",
                    error="",
                )
                logger.info("[WORKER] Job %s rechazado por una persona", job_id)
                return

            # --------------------------------------------------
            # CASO 3: EJECUCIÓN COMPLETADA
            # --------------------------------------------------
            if not snapshot.next:
                final_response = state_values.get("response", "")
                await update_job(
                    redis_client,
                    job_id,
                    status="DONE",
                    result=final_response,
                    result_status=state_values.get("status", "completado"),
                    approved=redis_bool(state_values.get("approved", False)),
                    requires_approval=redis_bool(
                        state_values.get("requires_approval", False)
                    ),
                    research_fallback_used=redis_bool(
                        state_values.get("research_fallback_used", False)
                    ),
                    formatting_fallback_used=redis_bool(
                        state_values.get("formatting_fallback_used", False)
                    ),
                    error="",
                )
                logger.info("[WORKER] Job %s completado", job_id)
                return

            raise RuntimeError(
                "El grafo terminó con nodos pendientes sin una interrupción "
                f"reconocida: {snapshot.next}"
            )

    except asyncio.TimeoutError:
        logger.error("[WORKER] Timeout en job=%s", job_id)
        try:
            await update_job(
                redis_client,
                job_id,
                status="FAILED",
                error=(
                    f"Se excedió el tiempo máximo "
                    f"({GRAPH_TIMEOUT_SECONDS}s)."
                ),
            )
        except Exception:
            logger.exception("[WORKER] No se pudo guardar el timeout en Redis")

    except Exception as exc:
        logger.exception("[WORKER] Error crítico en job=%s", job_id)
        try:
            await update_job(
                redis_client,
                job_id,
                status="FAILED",
                error=str(exc)[:1000],
            )
        except Exception:
            logger.exception("[WORKER] No se pudo guardar el error en Redis")

    finally:
        try:
            await redis_client.aclose()
        except Exception:
            logger.exception("[WORKER] Error cerrando el cliente Redis")
        logger.info("[WORKER] Proceso finalizado para job=%s", job_id)
