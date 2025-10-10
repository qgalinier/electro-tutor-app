# Electro-Tutor

## Descripción
Electro-Tutor es un asistente de chat interactivo diseñado para ayudar a estudiantes y entusiastas a comprender conceptos de física y electricidad. Utilizando un modelo de lenguaje avanzado, ofrece explicaciones claras, resuelve dudas y proporciona feedback sobre el aprendizaje. La aplicación consta de un frontend web moderno y responsivo, y un backend robusto construido con Flask.
Una cantidad considerable del código aquí mostrado fue generado utilizando otros LLM's especializados y dirigidos a la programación. Claude, Gemini, ChatGPT.

## Características
* **Chat Interactivo:** Conversaciones dinámicas sobre temas de electricidad y física.
* **Renderización MathJax:** Soporte para ecuaciones matemáticas y fórmulas para una claridad óptima.
* **Feedback de Usuario:** Sistema de calificación por estrellas y comentarios para mejorar las respuestas del tutor.
* **Diseño Responsivo:** Experiencia de usuario fluida en dispositivos de escritorio y móviles.

## Estructura del Proyecto

ELECTRO-TUTOR/
├── back-end/
│   ├── fine-tuning-data/    # Notebooks para fine-tuning del modelo
│   ├── .env                 # Variables de entorno para el backend (ej. API_KEY)
│   ├── app.py               # Lógica del servidor Flask
│   └── feedback.csv         # Almacenamiento de feedback de usuario
├── front-end/
│   ├── index.html           # Interfaz de usuario principal
│   ├── script.js            # Lógica del frontend (interacción, llamadas API)
│   ├── styles.css           # Estilos CSS de la aplicación
│   └── sw.js                # Service Worker (para PWA/offline caching)
├── requirements.txt         # Dependencias de Python para el backend
├── vercel.json              # Configuración de despliegue para Vercel
└── README.md                # Este archivo
└── .gitignore               # Archivos y carpetas a ignorar por Git

## Requisitos

* Python 3.8+
* pip (gestor de paquetes de Python)
* npm o yarn (para el frontend, si usas herramientas de construcción, aunque aquí es HTML/CSS/JS plano)
* Una cuenta de GitHub
* Una cuenta de Vercel (para despliegue)
* **API Key de tu proveedor de LLM (ej. OpenAI)**

## Instalación y Ejecución Local

Sigue estos pasos para configurar y ejecutar el proyecto en tu máquina local:

1.  **Clonar el Repositorio:**
    ```bash
    git clone [https://github.com/tu-usuario/electro-tutor.git](https://github.com/tu-usuario/electro-tutor.git)
    cd electro-tutor
    ```

2.  **Configurar el Backend:**
    * Crea un entorno virtual (recomendado):
        ```bash
        python -m venv venv
        source venv/bin/activate  # En Linux/macOS
        # venv\Scripts\activate  # En Windows
        ```
    * Instala las dependencias de Python:
        ```bash
        pip install -r requirements.txt
        ```
    * Crea un archivo `.env` en la carpeta `back-end/` y añade tu API Key:
        ```
        OPENAI_API_KEY="tu_openai_api_key_aqui"
        # O la variable de entorno que uses para tu LLM
        ```
    * Ejecuta el servidor Flask:
        ```bash
        python back-end/app.py
        ```
        El backend debería ejecutarse en `http://127.0.0.1:5000`.

3.  **Acceder al Frontend:**
    Abre `front-end/index.html` directamente en tu navegador web. El frontend se conectará automáticamente al backend local.

## Despliegue en Vercel

Para desplegar tu aplicación en Vercel:

1.  **Sube tu proyecto a GitHub:**
    Asegúrate de que todo tu código esté en un repositorio de GitHub.
    ```bash
    git init
    git add .
    git commit -m "Initial commit of Electro-Tutor AI"
    git branch -M main
    git remote add origin [https://github.com/tu-usuario/electro-tutor.git](https://github.com/tu-usuario/electro-tutor.git)
    git push -u origin main
    ```
    (Reemplaza `tu-usuario` y `electro-tutor` con tus datos.)

2.  **Conecta tu Repositorio en Vercel:**
    * Ve a [Vercel](https://vercel.com/) e inicia sesión.
    * Haz clic en "Add New Project" y selecciona tu repositorio `electro-tutor` de GitHub.
    * En la configuración del proyecto, Vercel debería detectar automáticamente la configuración de `vercel.json`.
    * **Configura las Variables de Entorno:**
        * Ve a "Settings" -> "Environment Variables" en la configuración de tu proyecto de Vercel.
        * Añade tu `OPENAI_API_KEY` (o la variable de tu LLM) aquí. Esto es crucial para que tu backend funcione en Vercel. **Nunca subas tus API Keys directamente a GitHub.**
    * Haz clic en "Deploy".

Vercel construirá y desplegará tu aplicación, haciendo que tu frontend y tu backend Flask sean accesibles bajo un dominio unificado.

## Contacto
Si tienes preguntas o sugerencias, no dudes en abrir un *issue* en este repositorio.
