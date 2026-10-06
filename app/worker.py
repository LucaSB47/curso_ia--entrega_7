import os
import redis.asyncio as aioredis
from dotenv import load_dotenv
from app.graph import get_compiled_graph

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

async def run_agent_task(job_id: str, task_data: dict):
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        # Actualizar estado a RUNNING en Redis
        await redis_client.hset(f"job:{job_id}", mapping={"status": "RUNNING"})
        
        graph = get_compiled_graph()
        config = {"configurable": {"thread_id": job_id}}
        
        # Ejecución del agente (esto genera la traza en LangSmith)
        result = await graph.ainvoke({"messages": [task_data["prompt"]]}, config=config)
        
        # Marcar como completado
        await redis_client.hset(f"job:{job_id}", mapping={"status": "DONE", "result": str(result.get("response", ""))})
        
    except Exception as e:
        # Capturar el error exacto en Redis para evitar loops infinitos
        await redis_client.hset(f"job:{job_id}", mapping={"status": "FAILED", "error": str(e)})
    finally:
        await redis_client.close()