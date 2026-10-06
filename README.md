# API de Producción Multi-Agente con LangGraph y Redis Cloud

Sistema backend asíncrono desarrollado en **FastAPI** y **LangGraph**, diseñado para la ejecución y orquestación de tareas multi-agente con persistencia de estados en tiempo real mediante **Redis Cloud**, soporte para intervención humana (`HITL` - *Human-in-the-Loop*) y observabilidad completa.

---

## 🚀 Características Principales

- **Arquitectura Asíncrona (FastAPI + Uvicorn):** procesamiento de solicitudes en segundo plano (`BackgroundTasks`) para evitar bloqueos en el hilo principal.
- **Persistencia y Estado en Redis Cloud:** almacenamiento seguro y centralizado de los metadatos y estados de cada tarea (`PENDING`, `PAUSED_FOR_APPROVAL`, etc.).
- **Orquestación con LangGraph:** manejo de grafos de estados y puntos de control avanzados para flujos de agentes conversacionales y analíticos.
- **Integración LLM:** impulsado por el modelo `gemini-3.8-flash` de Google.
- **Observabilidad Integral (LangSmith):** captura detallada de trazas, métricas de rendimiento (latencia p95), conteo de tokens y estimación de costos por cada ejecución del agente.
- **Interfaz Interactiva (Swagger UI):** documentación automática lista para pruebas en tiempo real.

---

## 🛠️ Requisitos Previos

- Python **3.10 o superior** (probado en Python 3.14).
- Una cuenta e instancia activa en **Redis Cloud**.
- API Keys de **Google Gemini** y **LangSmith** activas.

---

## 📦 Instalación y Configuración

1. **Clona o ubícate en la carpeta del proyecto:**

```powershell
   cd "ruta/a/tu/proyecto/entrega 7"
```

2. **Crea y activa un entorno virtual:**

```powershell
   python -m venv venv

   # En Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
```

3. **Instala las dependencias necesarias:**

```bash
   pip install fastapi uvicorn redis python-dotenv langgraph pydantic langchain-google-genai
```

4. **Configura las variables de entorno:**

   Crea un archivo llamado `.env` en la raíz del proyecto y añade tus credenciales:

```env
   # Redis
   REDIS_URL=redis://default:TU_PASSWORD@TU_HOST:TU_PUERTO

   # LangSmith (Observabilidad)
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
   LANGCHAIN_API_KEY=tu_api_key_de_langsmith
   LANGCHAIN_PROJECT=api-agente-produccion

   # Google Gemini
   GOOGLE_API_KEY=tu_api_key_de_google
```

---

## 🏃‍♂️ Ejecución del Servidor

Para iniciar la aplicación de manera limpia utilizando el entorno virtual configurado, puedes ejecutar el script de arranque dedicado:

```powershell
.\venv\Scripts\python run.py
```

O bien mediante Uvicorn directamente:

```powershell
python -m uvicorn app.main:app --reload
```

El servidor se iniciará localmente en: <http://127.0.0.1:8000>

---

## 📊 Observabilidad y Prueba de Carga (Pre-entrega 7)

El sistema cuenta con observabilidad configurada a través de **LangSmith** para monitorear el desempeño del agente.

Para validar la concurrencia y la captura de métricas exigida en la rúbrica, se lanzó una prueba de carga de **5 peticiones**.

> **Nota sobre Rate Limits (capa gratuita):** debido a los límites estrictos de la API de Gemini en su capa gratuita (Rate Limit 429 - 15 RPM máx.), las solicitudes múltiples concurrentes se manejan con un ligero retraso de seguridad (delay de 2 a 3 segundos) entre ejecuciones. Esto garantiza el procesamiento completo de todas las tareas y la captura de la latencia, tokens y costo en LangSmith sin generar bloqueos.

**Evidencia:**
En el directorio `screenshots/` se encuentra el archivo `image_3e4c3a.jpg`, el cual documenta las 5 trazas exitosas registradas en el panel de LangSmith.

---

## 📚 Documentación y Pruebas (Swagger UI)

Una vez que el servidor esté en marcha, abre tu navegador y accede a:

- **Swagger UI:** <http://127.0.0.1:8000/docs>

### Endpoints Disponibles

#### `POST /tasks`

**Descripción:** crea y encola una nueva tarea para el agente en segundo plano. Devuelve un identificador único (`job_id`) y el estado inicial `PENDING`.

**Ejemplo de payload:**

```json
{
  "prompt": "Analiza las métricas del sistema y genera un reporte",
  "requires_approval": true
}
```

#### `GET /tasks/{job_id}`

**Descripción:** consulta el estado actual de una tarea específica directamente desde Redis Cloud.

#### `POST /tasks/{job_id}/approve`

**Descripción:** permite reanudar una tarea que se encuentra pausada a la espera de autorización humana (HITL).

---

## 📂 Estructura del Proyecto

```text
entrega 7/
│
├── app/
│   ├── __init__.py
│   ├── main.py          # Definición de rutas FastAPI y endpoints
│   ├── worker.py        # Lógica de ejecución en segundo plano y agentes
│   ├── graph.py         # Configuración del grafo LangGraph y modelo Gemini
│   └── observability.py # Módulos de monitoreo y observabilidad
│
├── screenshots/
│   └── image_3e4c3a.jpg # Evidencia de métricas de LangSmith (Pre-entrega 7)
│
├── .env                 # Credenciales y variables de entorno
├── run.py               # Script auxiliar de ejecución limpia
├── requirements.txt     # Dependencias del proyecto
└── README.md            # Documentación del sistema
```