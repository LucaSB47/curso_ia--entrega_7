# API de Producción Multi-Agente con LangGraph, Redis y Observabilidad

API REST asíncrona desarrollada con **FastAPI** para la orquestación de un sistema multi-agente con **LangGraph**, persistencia de estados y checkpoints en **Redis**, monitoreo mediante **LangSmith** y un flujo interactivo de aprobación humana (**Human-in-the-Loop**).

---

## 🏗️ Estructura del proyecto

```text
curso_ia--entrega_7/
├── app/
│   ├── main.py                  # Endpoints FastAPI, inyección de dependencias y pool de Redis
│   ├── graph.py                 # Orquestador LangGraph, nodos especializados e interrupciones
│   ├── worker.py                # Worker asíncrono, AsyncRedisSaver y Command(resume)
│   └── observability.py         # Configuración de trazas e instrumentación de LangSmith
├── screenshots/
│   ├── trazas.png               # Evidencia del árbol de nodos y ejecuciones del agente
│   └── metricas_langsmith.png   # Latencia P95, costos y cinco ejecuciones en paralelo
├── .env.example                 # Plantilla de variables de entorno
├── .gitignore                   # Exclusión de credenciales, entornos virtuales y cachés
├── Dockerfile                   # Imagen Docker de la API
├── docker-compose.yml           # Orquestación de la API y Redis Stack
├── requirements.txt             # Dependencias del proyecto
├── run.py                       # Script de inicialización de Uvicorn
└── test.py                      # Prueba de carga concurrente con cinco peticiones
```

---

## ⚡ Características clave

### 1. Orquestación asíncrona

El endpoint `POST /tasks` recibe solicitudes y devuelve inmediatamente un identificador `job_id`, delegando el procesamiento en segundo plano para evitar bloquear la respuesta de la API.

### 2. Pool de conexiones a Redis

Se utiliza un `ConnectionPool` reutilizable junto con la inyección de dependencias de FastAPI mediante `Depends`, reduciendo la necesidad de crear y cerrar conexiones manualmente en cada petición.

### 3. Human-in-the-Loop (HITL)

El flujo de aprobación humana depende del campo booleano `requires_approval`, enviado en el cuerpo de `POST /tasks` y propagado por el worker al estado inicial de LangGraph.

- Si `requires_approval` es `true`, el grafo pasa del nodo de investigación a `human_approval`, donde `interrupt()` pausa la ejecución hasta recibir una decisión externa.
- Si `requires_approval` es `false`, el grafo omite el nodo de aprobación y continúa directamente al nodo de formateo.
- Cuando una tarea está pausada, puede reanudarse mediante `Command(resume=...)`, conservando el `thread_id` asociado al trabajo para recuperar su checkpoint.

En esta versión, el valor de `requires_approval` lo define quien envía la solicitud; el sistema no determina automáticamente si una tarea es crítica.

### 4. Resiliencia y tolerancia a fallos

Se contemplan errores de servicios externos, como respuestas HTTP `429`, `503` o `504`, mediante mecanismos de manejo de excepciones y recuperación.

Según el resultado del procesamiento, la tarea puede finalizar correctamente (`DONE`) o registrar un fallo (`FAILED`).

---

## ⚙️ Instalación y configuración

### 1. Requisitos previos

- Python 3.12 o superior.
- Redis activo en `localhost:6379` o disponible mediante Docker.
- Una clave de API de Google para el modelo de lenguaje configurado.
- Una clave de API de LangSmith para la observabilidad.

### 2. Crear y activar el entorno virtual

En Windows, utilizando PowerShell:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

Si utilizás CMD:

```bat
venv\Scripts\activate.bat
```

En Linux o macOS:

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar las variables de entorno

Creá un archivo `.env` en la raíz del proyecto, tomando como referencia `.env.example`.

```dotenv
# Redis
REDIS_URL=redis://localhost:6379

# Modelo de lenguaje
GEMINI_MODEL=gemini-3.8-flash
GOOGLE_API_KEY=tu_google_api_key_aqui

# Configuración del grafo
GRAPH_TIMEOUT_SECONDS=60

# Observabilidad con LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=tu_langsmith_api_key_aqui
LANGCHAIN_PROJECT=api-agente-produccion
```

**Importante:** verificá que el identificador `gemini-3.8-flash` corresponda a un modelo disponible para la API y a la integración utilizada en el proyecto.

No subas el archivo `.env` al repositorio. Las claves de API deben mantenerse privadas.

---

## 🚀 Modos de ejecución

### Opción A: ejecución local

Iniciá la API con:

```bash
python run.py
```

También podés utilizar Uvicorn directamente:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

La documentación interactiva de Swagger estará disponible en:

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Opción B: despliegue con Docker Compose

Para construir las imágenes e iniciar los servicios:

```bash
docker compose up --build
```

Para ejecutar los servicios en segundo plano:

```bash
docker compose up --build -d
```

Para detener los servicios:

```bash
docker compose down
```

---

## 🧪 Prueba de carga concurrente

El proyecto incluye `test.py`, un script diseñado para enviar cinco solicitudes simultáneas al endpoint `POST /tasks`.

Ejecutalo con:

```bash
python test.py
```

El script utiliza `httpx.AsyncClient` y `asyncio.gather` para ejecutar las peticiones de forma concurrente.

El objetivo es verificar que la API responda con el código HTTP `202 Accepted` y un `job_id` para cada solicitud, sin esperar a que finalice el procesamiento completo de los agentes.

**Nota:** responder con `202 Accepted` confirma que la solicitud fue aceptada para su procesamiento, pero no garantiza por sí solo que el trabajo termine correctamente. El resultado debe verificarse consultando el estado de cada tarea.

---

## 📊 Observabilidad y monitoreo

Las evidencias de monitoreo se encuentran en la carpeta `screenshots/`.

### 1. Métricas de carga y costo

Archivo: `screenshots/metricas_p95_costo.png`

La captura está destinada a mostrar:

- El resultado de cinco ejecuciones concurrentes.
- La cantidad de ejecuciones exitosas y fallidas.
- El costo registrado por las ejecuciones.
- Los percentiles de latencia, incluido P95.

### 2. Trazas del agente

Archivo: `screenshots/trazas.png`

La captura permite documentar las trazas de ejecución y el recorrido entre los nodos del grafo, incluidos:

- `research_node`
- `human_approval`
- `formatting_node`

Las métricas y los resultados descritos deben coincidir con los datos reales registrados en LangSmith.

---

## 🔄 Ciclo de vida de los trabajos

Los estados previstos para una tarea son:

| Estado | Descripción |
|---|---|
| `PENDING` | La tarea fue recibida y está pendiente de ejecución. |
| `RUNNING` | El worker está ejecutando el grafo. |
| `PAUSED_FOR_APPROVAL` | El flujo está detenido y espera aprobación humana. |
| `RESUMING` | Se solicitó reanudar la ejecución. |
| `DONE` | El procesamiento finalizó correctamente. |
| `REJECTED` | La tarea fue rechazada explícitamente. |
| `FAILED` | La ejecución terminó con un error no recuperado o un timeout. |

La transición entre estados depende de la lógica implementada en el worker y de las respuestas de los nodos del grafo.

---

## 🙋 Cómo probar el flujo Human-in-the-Loop

Podés probar el proceso completo desde Swagger.

### Paso 1. Crear una tarea que requiera aprobación

Realizá una petición:

```http
POST /tasks
```

Cuerpo JSON:

```json
{
  "prompt": "Analizar caso de estudio",
  "requires_approval": true
}
```

La API debe devolver una respuesta `202 Accepted` con un identificador `job_id`. La tarea avanzará hasta `human_approval` y quedará pausada hasta recibir una decisión externa.

Para crear una tarea que **no** requiera aprobación, enviá `"requires_approval": false`. En ese caso, el grafo omitirá el nodo `human_approval` y continuará directamente al nodo de formateo.

Ejemplo ilustrativo de respuesta:

```json
{
  "job_id": "identificador-de-la-tarea",
  "status": "PENDING"
}
```

La estructura exacta de la respuesta dependerá de la implementación del endpoint.

### Paso 2. Consultar el estado

Utilizá el identificador obtenido:

```http
GET /tasks/{job_id}
```

Para la tarea que requiere aprobación, esperá hasta que el estado sea `PAUSED_FOR_APPROVAL`.

### Paso 3. Enviar la aprobación

Realizá una petición:

```http
POST /tasks/{job_id}/approve
```

Cuerpo JSON para aprobar:

```json
{
  "approved": true
}
```

Para rechazar la tarea, enviá:

```json
{
  "approved": false
}
```

La decisión debe reanudar el grafo utilizando el checkpoint persistido y el `thread_id` correspondiente.

### Paso 4. Confirmar la finalización

Volvé a consultar:

```http
GET /tasks/{job_id}
```

El estado puede pasar por `RESUMING` antes de alcanzar `DONE`, siempre que el procesamiento termine correctamente.

Si se rechaza la aprobación, el sistema debe seguir la ruta de rechazo definida en el grafo.

---

## 🔐 Buenas prácticas de producción

- Mantener las claves de API fuera del código fuente y del control de versiones.
- Declarar y fijar las versiones de las dependencias en `requirements.txt`.
- Reutilizar el pool de conexiones a Redis y cerrar los recursos durante el apagado de la aplicación.
- Definir límites de tiempo para las llamadas externas y el procesamiento del grafo.
- Registrar errores y transiciones de estado para facilitar el diagnóstico.
- Validar las solicitudes y las decisiones de aprobación humana.
- Garantizar que las tareas puedan recuperarse después de una interrupción del servicio.
- Utilizar un mecanismo de ejecución en segundo plano apropiado para trabajos duraderos y controlar los reintentos.
- Verificar que Redis tenga una política de persistencia y seguridad adecuada para el entorno de despliegue.

**Consideración de arquitectura:** `BackgroundTasks` de FastAPI es útil para trabajos sencillos, pero no constituye por sí solo una cola de trabajos duradera. Si necesitás garantizar la recuperación de tareas ante reinicios o caídas de la API, conviene utilizar un worker independiente con una cola persistente y mecanismos de recuperación.

---

## 📌 Conclusión

Este proyecto propone una arquitectura asíncrona para ejecutar flujos multi-agente con LangGraph, almacenar estados y checkpoints en Redis, incorporar aprobaciones humanas y observar las ejecuciones mediante LangSmith.

La combinación de estos componentes permite organizar tareas complejas, realizar seguimiento de su ciclo de vida y establecer una base para un servicio de IA preparado para evolucionar hacia un entorno de producción.
