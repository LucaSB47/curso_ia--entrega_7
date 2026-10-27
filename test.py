import asyncio
import httpx
import time

async def enviar_y_monitorear(cliente, i):
    # 1. Retraso escalonado (3 segundos x índice) para evitar el Error 429 de Gemini
    await asyncio.sleep(i * 3)
    
    url = "http://127.0.0.1:8000/tasks"
    payload = {
        "prompt": f"Genera un dato curioso sobre la historia del hardware. Petición {i}",
        "requires_approval": False
    }
    
    print(f"[{i}] Lanzando petición...")
    response = await cliente.post(url, json=payload)
    
    # 2. Comprobar que FastAPI responde de forma asíncrona correctamente (Requisito del profesor)
    if response.status_code != 202:
        print(f"[{i}] ❌ Error en la API: Código {response.status_code}")
        return None
        
    job_data = response.json()
    job_id = job_data.get("job_id")
    print(f"[{i}] Aceptada (202 Accepted). Job ID: {job_id}. Monitoreando estado...")
    
    # 3. Polling para confirmar que el trabajo no caiga en fallback y termine bien
    while True:
        await asyncio.sleep(2) # Espera antes de volver a consultar
        res_estado = await cliente.get(f"{url}/{job_id}")
        estado_actual = res_estado.json().get("status")
        
        if estado_actual == "DONE":
            print(f"[{i}] ✅ Trabajo completado con éxito (DONE).")
            break
        elif estado_actual in ["FAILED", "REJECTED"]:
            print(f"[{i}] ⚠️ El trabajo terminó en estado: {estado_actual}.")
            break
            
    return job_id

async def main():
    inicio = time.time()
    # Aumentamos el timeout del cliente por si la IA demora en responder
    async with httpx.AsyncClient(timeout=30.0) as cliente:
        # Creamos y ejecutamos las 5 tareas concurrentes
        tareas = [enviar_y_monitorear(cliente, i) for i in range(1, 6)]
        await asyncio.gather(*tareas)
    
    fin = time.time()
    print(f"\n¡Prueba de carga y monitoreo finalizada en {fin - inicio:.2f} segundos!")

if __name__ == "__main__":
    asyncio.run(main())