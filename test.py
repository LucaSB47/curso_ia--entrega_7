import asyncio
import httpx
import time

async def enviar_peticion(cliente, i):
    url = "http://127.0.0.1:8000/tasks"
    payload = {
        "prompt": f"Genera un dato curioso sobre la informática. Petición {i}",
        "requires_approval": False
    }
    print(f"Lanzando petición {i}...")
    response = await cliente.post(url, json=payload)
    return response.json()

async def main():
    inicio = time.time()
    async with httpx.AsyncClient() as cliente:
        tareas = [enviar_peticion(cliente, i) for i in range(1, 6)]
        resultados = await asyncio.gather(*tareas)
    
    fin = time.time()
    print(f"\n¡Prueba terminada en {fin - inicio:.2f} segundos!")
    print("Resultados de los jobs generados:")
    for res in resultados:
        print(res)

if __name__ == "__main__":
    asyncio.run(main())