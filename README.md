# traduccion_reunion.py
Script en Python para traducir en tiempo casi real reuniones en inglés (Zoom, Meet, Teams, etc.). Escucha el audio del PC, usa AssemblyAI para pasarlo a texto y DeepL API Free para traducirlo al español y mostrar subtítulos en pantalla.

## Configurar API keys (.env)

Crea un archivo `.env` en la misma carpeta que los archivos `.py` con este contenido:

ASSEMBLYAI_API_KEY=TU_API_KEY_DE_ASSEMBLYAI
DEEPL_API_KEY=TU_API_KEY_DE_DEEPL
