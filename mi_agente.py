import os
from crewai import Agent, Task, Crew
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# 1. Cargamos las llaves
load_dotenv()

# Actualizamos a la versión activa del modelo de Google
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

# 3. Forzamos al agente a usar el modelo de Google
analista = Agent(
    role='Senior Developer y Consultor',
    goal='Optimizar el código de descarga de videos',
    backstory='Experto en automatización para negocios digitales.',
    llm=llm,                # <--- USA TU GEMINI
    allow_delegation=False, # <--- EVITA QUE BUSQUE OTROS MODELOS
    verbose=True
)

tarea = Task(
    description='Analiza youtube_downloader.py y sugiere una mejora.',
    expected_output='Una breve explicación de la mejora.',
    agent=analista
)

equipo = Crew(agents=[analista], tasks=[tarea])
print(equipo.kickoff())