import os
from dotenv import load_dotenv

def setup_observability():
    # Cargar variables del archivo .env de forma segura
    load_dotenv()
    
    # Rescatar la clave de forma segura desde el entorno
    api_key = os.environ.get("LANGCHAIN_API_KEY", "")

    # Variables clásicas (las más estables)
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    os.environ["LANGCHAIN_PROJECT"] = "api-agente-produccion"
    if api_key:
        os.environ["LANGCHAIN_API_KEY"] = api_key
    
    # Variables nuevas (por redundancia)
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
    os.environ["LANGSMITH_PROJECT"] = "api-agente-produccion"
    if api_key:
        os.environ["LANGSMITH_API_KEY"] = api_key