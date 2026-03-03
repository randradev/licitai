# -*- coding: utf-8 -*-
"""
Módulo: Analista de Inteligencia (AIAnalyst)
-------------------------------------------
Este módulo orquesta la evaluación estratégica de licitaciones utilizando 
modelos de lenguaje de gran escala (LLM), específicamente Google Gemini.

Responsabilidades:
1. Gestionar la comunicación con la API de Google Generative AI.
2. Implementar 'Prompt Engineering' para contextualizar el análisis según el perfil de empresa.
3. Transformar datos no estructurados (scraping) en información estructurada (JSON).
4. Ejecutar la reparación semántica de datos incompletos.
"""

import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

class AIAnalyst:
    """
    Clase encargada de la inferencia y análisis estratégico mediante IA.
    
    Utiliza el modelo Gemini para procesar el cuerpo de texto extraído y 
    determinar la viabilidad técnica y comercial de una licitación.
    """

    def __init__(self, db_manager):
        """
        Inicializar el motor de IA y configurar la autenticación.

        Args:
            db_manager (DatabaseManager): Instancia del gestor de base de datos 
                                          para recuperación de contexto.
        """
        load_dotenv()
        self.db = db_manager
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("❌ Error Crítico: No se encontró GEMINI_API_KEY en las variables de entorno.")
            
        genai.configure(api_key=api_key)
        # Se utiliza gemini-3-flash por su baja latencia y eficiencia en procesamiento de texto
        self.model = genai.GenerativeModel('gemini-3-flash-preview')

    def analizar_licitacion(self, id_externo):
        """
        Ejecutar el pipeline completo de análisis para una licitación.
        
        Proceso:
        1. Recuperar contexto (Perfil + Licitación).
        2. Inyectar prompts especializados.
        3. Realizar inferencia.
        4. Persistir resultados y ejecutar autoreparación de datos.

        Args:
            id_externo (str): Identificador único de la licitación a analizar.

        Returns:
            dict: Resultados del análisis (Score, Veredicto, Riesgos) o None si falla.
        """
        # 1. Recuperación de contexto desde la persistencia
        perfil = self.db.obtener_perfil()
        licitaciones = self.db.obtener_licitaciones()
        licit = next((l for l in licitaciones if l['id_externo'] == id_externo), None)

        # Validación de integridad: Si no hay descripción extraída, no hay base para el análisis
        if not licit or not licit.get('descripcion_pro'):
            print(f"⚠️ Advertencia: No hay descripción técnica para la licitación {id_externo}")
            return None

        # 2. Ingeniería de Contexto (Prompt Engineering)
        # Se utiliza una estructura de 'System Prompt' inyectada para guiar el comportamiento del modelo
        prompt = f"""
        Actúa como un Consultor experto en Licitaciones Públicas en Chile (Mercado Público). 
        Analiza la conveniencia de la siguiente licitación según el perfil estratégico de mi empresa.

        --- PERFIL ESTRATÉGICO DE MI EMPRESA ---
        - Propuesta de Valor: {perfil['bio_estrategica']}
        - Objetivos de Búsqueda (Keywords+): {perfil['keywords_pos']}
        - Filtros de Exclusión (Keywords-): {perfil['keywords_neg']}

        --- DATOS TÉCNICOS DE LA LICITACIÓN ---
        - ID: {id_externo}
        - Título Referencial: {licit['titulo']}
        - Organismo Referencial: {licit['organismo']}
        - Corpus Extraído (Contenido Bruto): 
        {licit['descripcion_pro']}

        --- REQUISITOS DE SALIDA (FORMATO JSON ESTRICTO) ---
        Analiza el 'Corpus Extraído' para identificar la información real y genera un JSON con:
        {{
            "titulo_recuperado": "Título oficial completo encontrado",
            "organismo_recuperado": "Nombre legal de la institución compradora",
            "comportamiento_pago": "Menciona reclamos de pago encontrados o historial",
            "score_ia": (Entero del 1 al 10 según idoneidad),
            "veredicto": "Resumen ejecutivo de conveniencia (máx 2 líneas)",
            "puntos_criticos": ["Lista de 3 requerimientos técnicos clave"],
            "riesgos": ["Lista de 2 riesgos potenciales encontrados"],
            "motivo_archivo": "Explicación breve de por qué se descarta (solo si score < 6)"
        }}
        """

        # 3. Ejecución de la inferencia y procesamiento de respuesta
        try:
            response = self.model.generate_content(prompt)
            
            # Limpieza de delimitadores Markdown en la respuesta del modelo
            clean_text = response.text.replace('```json', '').replace('```', '').strip()
            data_ia = json.loads(clean_text)
            
            # 4. Fase de Persistencia y Post-procesamiento
            
            # Almacenar el análisis técnico y el score de prioridad
            self.db.guardar_analisis_ia(
                id_externo, 
                data_ia['score_ia'], 
                data_ia,
                data_ia.get('motivo_archivo')
            )

            # Auto-reparación semántica:
            # Si el scraping inicial falló o fue incompleto, se actualizan los datos 
            # maestros usando la inferencia semántica del modelo IA.
            self.db.reparar_datos_licitacion(
                id_externo,
                data_ia.get('titulo_recuperado'),
                data_ia.get('organismo_recuperado'),
                data_ia.get('comportamiento_pago')
            )

            return data_ia

        except Exception as e:
            print(f"❌ Error en pipeline de IA para {id_externo}: {str(e)}")
            return None