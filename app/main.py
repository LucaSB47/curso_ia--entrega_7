import os
import uuid
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel
import redis.asyncio as aioredis
from dotenv import load_dotenv

from app.worker import run_agent_task
from app.observability import setup_observability

# Carga las variables de entorno
load_dotenv()
setup_observability()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# 1. Crear un Pool de conexiones global y reutilizable (¡Esto es lo que pide el profe!)
redis_pool = aioredis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)

# 2. Función de Inyección de Dependencias (Dependency Injection)
async def get_redis():
    client = aioredis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.close() # Libera la conexión de vuelta al pool de forma segura

app = FastAPI(title="API de Producción Multi-Agente", version="1.0.0")

class TaskRequest(BaseModel):
    prompt: str
    requires_approval: bool = False

@app.post("/tasks", status_code=202)
async def create_task(
    task: TaskRequest, 
    background_tasks: BackgroundTasks,
    redis_client: aioredis.Redis = Depends(get_redis)  # <-- Inyección aquí
):
    job_id = str(uuid.uuid4())
    
    # Registrar job inicial en Redis
    await redis_client.hset(f"job:{job_id}", mapping={"status": "PENDING", "prompt": task.prompt})
    
    # Encolar en segundo plano sin bloquear. (Usamos model_dump() que es la forma moderna de Pydantic)
    background_tasks.add_task(run_agent_task, job_id, task.model_dump())
    
    return {"job_id": job_id, "status": "PENDING"}

@app.get("/tasks/{job_id}")
async def get_task_status(
    job_id: str,
    redis_client: aioredis.Redis = Depends(get_redis)  # <-- Inyección aquí
):
    job_data = await redis_client.hgetall(f"job:{job_id}")
    
    if not job_data:
        raise HTTPException(status_code=404, detail="Job no encontrado")
        
    return job_data

@app.post("/tasks/{job_id}/approve")
async def approve_task(
    job_id: str, 
    background_tasks: BackgroundTasks,
    redis_client: aioredis.Redis = Depends(get_redis)  # <-- Inyección aquí
):
    status = await redis_client.hget(f"job:{job_id}", "status")
    
    if not status or status != "PAUSED_FOR_APPROVAL":
        raise HTTPException(status_code=400, detail="El job no está pausado para aprobación.")
        
    # Reanudar tarea aprobada en segundo plano
    background_tasks.add_task(run_agent_task, job_id, {"prompt": "Aprobado", "requires_approval": False})
    return {"job_id": job_id, "status": "RESUMING"}