# -*- coding: utf-8 -*-
"""
Módulo: Orquestador Principal (Main Pipeline)
--------------------------------------------
Este script coordina el flujo de trabajo completo de LicitAI. 
Actúa como el pegamento entre el descubrimiento (API), la extracción 
técnica (Selenium), el análisis estratégico (IA) y la persistencia (SQLite).

Flujo de ejecución:
1. Descubrimiento: Identifica nuevas licitaciones vía API.
2. Filtrado: Descarta las que no cumplen con los criterios o ya existen.
3. Procesamiento Profundo: Extrae contenido web y genera insights con Gemini.
"""

import time
from datetime import datetime
from core.database_mgr import DatabaseManager
from core.scraper import LicitacionScraper
from core.ai_analyst import AIAnalyst

def ejecutar_pipeline():
    """
    Ejecuta el ciclo de vida completo de procesamiento de licitaciones.
    Diseñado para ser invocado manualmente desde la UI o mediante tareas cron.
    """
    print("🚀 LicitAI: Iniciando ciclo de procesamiento...")

    # Inicialización de dependencias e inyección de base de datos
    db = DatabaseManager()
    scraper = LicitacionScraper(db)
    analyst = AIAnalyst(db)

    # -------------------------------------------------------
    # FASE 1: DESCUBRIMIENTO (API)
    # -------------------------------------------------------
    # Consulta masiva al endpoint oficial de Mercado Público
    licitaciones_dia = scraper.ejecutar_pipeline_descubrimiento()

    if not licitaciones_dia:
        print("☕ No se encontraron licitaciones nuevas hoy. Fin del ciclo.")
        return
    
    # -------------------------------------------------------
    # FASE 2: FILTRADO Y GUARDADO INICIAL
    # -------------------------------------------------------
    # Pre-procesamiento para registrar solo lo estrictamente necesario antes de la IA
    codigos_a_procesar = []

    for l in licitaciones_dia:
        id_ext = l['CodigoExterno']
        if not db.existe_licitacion(id_ext):
            # Normalización de metadatos básicos
            fecha_hoy = datetime.now().strftime("%d/%m/%Y")
            
            data_db = {
                'id_externo': id_ext,
                'titulo': l['Nombre'],
                'organismo': l.get('OrganismoCompleto', 'No disponible'),
                'fecha_cierre': l.get('FechaCierre', 'Sin fecha')
            }
            db.guardar_licitacion(data_db)
            codigos_a_procesar.append(id_ext)

    if not codigos_a_procesar:
        print("✅ Todas las licitaciones encontradas ya fueron procesadas previamente.")
        return
    
    print(f"📦 Se detectaron {len(codigos_a_procesar)} licitaciones nuevas para analizar.")

    # -------------------------------------------------------
    # FASE 3: EXTRACCIÓN Y ANÁLISIS IA
    # -------------------------------------------------------
    # Control de cuotas: Limitar procesamiento para optimizar tiempos y tokens
    MAX_PROCESAR = 5
    procesados = 0

    for id_ext in codigos_a_procesar:
        
        if procesados >= MAX_PROCESAR:
            print(f"\n✋ Se alcanzó el límite de {MAX_PROCESAR} por esta sesión.")
            break
        
        print(f"\n--- Procesando ({procesados+1}/{MAX_PROCESAR}): {id_ext} ---")

        # ---------------------------------
        # A. EXTRACCIÓN PROFUNDA (SELENIUM)
        # ---------------------------------
        # Navegación automatizada para obtener el corpus técnico
        detalle = scraper.extraer_detalle_licitacion(id_ext)

        if detalle and detalle['descripcion_pro'] != "No se pudo extraer el detalle técnico.":
            
            # Sanitización y formateo de fecha de publicación al estándar local
            f_pub_raw = detalle.get('fecha_publicacion')
            try:
                f_pub_local = datetime.strptime(f_pub_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                f_pub_local = datetime.now().strftime("%d/%m/%Y")

            # Actualización de datos maestros con información de la ficha técnica
            db.actualizar_datos_maestros(
                id_ext, 
                titulo=detalle.get('titulo_oficial'), 
                organismo=detalle.get('organismo'),
                fecha_pub=f_pub_local,
                reclamo_pago=detalle.get('reclamo_pago')
            )

            # Persistencia del corpus textual para su posterior procesamiento por LLM
            db.actualizar_detalle_profundo(id_ext, detalle['link'], detalle['descripcion_pro'])
            print(f"🔍 Extracción web completada.")

            # ---------------------------------
            # B. ANÁLISIS ESTRATÉGICO (GEMINI)
            # ---------------------------------
            # Inferencia mediante IA para generar score y veredicto
            print(f"🧠 Consultando a la IA...")
            analis = analyst.analizar_licitacion(id_ext)

            if analis:
                # Presentación de resultados en terminal (Consola)
                score = analis.get('score_ia', 0)
                
                print(f"📌 TÍTULO: {analis.get('titulo_recuperado', 'No detectado')}")
                print(f"🏢 ORGANISMO: {analis.get('organismo_recuperado', 'Cargando...')}")
                print(f"📅 PUB. OFICIAL: {f_pub_local}")
                print(f"💳 COMPORTAMIENTO PAGO: {analis.get('comportamiento_pago', 'No informado')}")
                print(f"🔗 LINK: {detalle['link']}")
                print("-" * 70)

                print(f"\n🎯 ANÁLISIS COMPLETADO - SCORE: {score}/10")
                print(f"📝 VEREDICTO: {analis.get('veredicto')}")
                
                print("\n📌 PUNTOS CRÍTICOS:")
                for p in analis.get('puntos_criticos', []): print(f"   • {p}")
                
                print("\n⚠️ RIESGOS:")
                for r in analis.get('riesgos', []): print(f"   • {r}")
                
                if score < 5:
                    print(f"\n📂 MOTIVO DE ARCHIVO: {analis.get('motivo_archivo')}")
                
                procesados += 1 
            else:
                print(f"⚠️ La IA no pudo procesar esta licitación.")
        else:
            print(f"❌ Falló la extracción técnica para {id_ext}.")

        # Gestión de estabilidad: Evitar bloqueos por parte del servidor destino (Mercado Público)
        print(f"💤 Esperando 5 segundos para estabilizar la siguiente carga...")
        time.sleep(5)

    print("\n" + "="*50)
    print("✅ CICLO COMPLETADO CON ÉXITO")
    print("="*50)

# Punto de entrada para ejecución directa desde CLI
if __name__ == "__main__":
    ejecutar_pipeline()