import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from app.observability import setup_observability
from app.worker import run_agent_task

load_dotenv()
setup_observability()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Pool reutilizable para las peticiones HTTP.
redis_pool = aioredis.ConnectionPool.from_url(
    REDIS_URL,
    decode_responses=True,
)


async def get_redis() -> AsyncIterator[aioredis.Redis]:
    """Proporciona un cliente Redis por petición usando el pool compartido."""
    client = aioredis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        # Como el pool se comparte, cerrar el cliente no debe destruirlo.
        await client.aclose()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Cierra el pool al apagar ordenadamente la API."""
    try:
        yield
    finally:
        await redis_pool.aclose()


app = FastAPI(
    title="API de Producción Multi-Agente",
    version="1.1.0",
    lifespan=lifespan,
)


class TaskRequest(BaseModel):
    prompt: str = Field(min_length=1, description="Instrucción para el agente")
    requires_approval: bool = Field(
        default=False,
        description="Indica si el grafo debe pausarse para aprobación humana",
    )


class ApproveRequest(BaseModel):
    approved: bool = Field(
        description="true para aprobar; false para rechazar la tarea",
    )


@app.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    task: TaskRequest,
    background_tasks: BackgroundTasks,
    redis_client: aioredis.Redis = Depends(get_redis),
):
    prompt = task.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El prompt no puede estar vacío.",
        )

    job_id = str(uuid.uuid4())
    requires_approval = task.requires_approval

    # Guardamos el estado inicial y el requisito de aprobación en Redis.
    await redis_client.hset(
        f"job:{job_id}",
        mapping={
            "status": "PENDING",
            "prompt": prompt,
            "requires_approval": (
                "true" if requires_approval else "false"
            ),
            "approved": "false",
            "error": "",
        },
    )

    # Se pasa model_dump() al worker; incluye requires_approval.
    task_data = {
        "prompt": prompt,
        "requires_approval": requires_approval,
    }
    background_tasks.add_task(run_agent_task, job_id, task_data)

    return {
        "job_id": job_id,
        "status": "PENDING",
        "requires_approval": requires_approval,
    }


@app.get("/tasks/{job_id}")
async def get_task_status(
    job_id: str,
    redis_client: aioredis.Redis = Depends(get_redis),
):
    job_data = await redis_client.hgetall(f"job:{job_id}")
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job no encontrado.",
        )
    return job_data


@app.post("/tasks/{job_id}/approve", status_code=status.HTTP_202_ACCEPTED)
async def approve_task(
    job_id: str,
    payload: ApproveRequest,
    background_tasks: BackgroundTasks,
    redis_client: aioredis.Redis = Depends(get_redis),
):
    job_key = f"job:{job_id}"
    job_data = await redis_client.hgetall(job_key)

    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job no encontrado.",
        )

    if job_data.get("status") != "PAUSED_FOR_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El job no está pausado para aprobación.",
        )

    # Evita que dos solicitudes intenten aprobar/rechazar el mismo job.
    # Para cargas multiinstancia, reemplazar por una operación Redis atómica.
    await redis_client.hset(
        job_key,
        mapping={
            "status": "RESUMING",
            "approval_decision": (
                "approved" if payload.approved else "rejected"
            ),
        },
    )

    task_data = {
        "is_resume": True,
        "approved": payload.approved,
    }
    background_tasks.add_task(run_agent_task, job_id, task_data)

    return {
        "job_id": job_id,
        "status": "RESUMING",
        "approved": payload.approved,
    }
