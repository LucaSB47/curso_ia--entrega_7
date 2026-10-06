from dotenv import load_dotenv
load_dotenv()  # <-- Esto es vital para que las credenciales de LangSmith y Gemini se carguen al iniciar FastAPI

import os
from fastapi import FastAPI, BackgroundTasks
# ... resto de tus imports ...
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import uuid
import redis.asyncio as aioredis
import os
from dotenv import load_dotenv
from app.worker import run_agent_task
from app.observability import setup_observability

# Carga las variables de entorno desde el archivo .env
load_dotenv()

setup_observability()

app = FastAPI(title="API de Producción Multi-Agente", version="1.0.0")

# Lee la URL de Redis Cloud definida en el archivo .env
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class TaskRequest(BaseModel):
    prompt: str
    requires_approval: bool = False

@app.post("/tasks", status_code=202)
async def create_task(task: TaskRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    
    # Registrar job inicial en Redis
    await redis_client.hset(f"job:{job_id}", mapping={"status": "PENDING", "prompt": task.prompt})
    await redis_client.close()
    
    # Encolar en segundo plano sin bloquear
    background_tasks.add_task(run_agent_task, job_id, task.dict())
    
    return {"job_id": job_id, "status": "PENDING"}

@app.get("/tasks/{job_id}")
async def get_task_status(job_id: str):
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    job_data = await redis_client.hgetall(f"job:{job_id}")
    await redis_client.close()
    
    if not job_data:
        raise HTTPException(status_code=404, detail="Job no encontrado")
        
    return job_data

@app.post("/tasks/{job_id}/approve")
async def approve_task(job_id: str, background_tasks: BackgroundTasks):
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    status = await redis_client.hget(f"job:{job_id}", "status")
    
    if not status or status != "PAUSED_FOR_APPROVAL":
        await redis_client.close()
        raise HTTPException(status_code=400, detail="El job no está pausado para aprobación.")
        
    await redis_client.close()
    
    # Reanudar tarea aprobada en segundo plano
    background_tasks.add_task(run_agent_task, job_id, {"prompt": "Aprobado", "requires_approval": False})
    return {"job_id": job_id, "status": "RESUMING"}