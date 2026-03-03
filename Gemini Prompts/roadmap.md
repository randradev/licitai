# ROADMAP

## Fase 1: Cimientos y Configuración
Objetivo: Tener el backend operativo con la estructura del ERD y la configuración global.
1. Setup Django: Crear el proyecto licitai_core y la app principal tenders.
2. Modelado (ERD): Implementar los modelos GlobalConfig, Keyword, Tender, Attachment, Analysis y TenderManagement en [models.py](http://models.py/).
3. Seguridad Base: Implementar el cifrado para el api_ticket (usando cryptography).
4. API Inicial (DRF): CRUD de Keywords y endpoints de configuración global.


## Fase 2: Motor de Descubrimiento - Nivel 1
Objetivo: Traer datos reales de Mercado Público.
1. Cliente API: Crear un servicio en Python para interactuar con la API de Mercado Público (consumo de licitaciones por fecha/keywords).
2. Lógica de Sincronización: Script/Comando de Django para descargar licitaciones y guardarlas en TENDER.
3. Filtro de Relevancia: Lógica para marcar licitaciones que coinciden con las "Keywords Positivas".


## Fase 3: Procesamiento Asíncrono e IA - Nivel 2
Objetivo: El "cerebro" del sistema.
1. Infraestructura: Configurar Redis y Celery para tareas en segundo plano.
2. Scraper de Adjuntos: Implementar el scraper (Selenium/Playwright) para entrar a la ficha técnica y capturar links de documentos.
3. Integración Gemini: Crear el prompt y la lógica para enviar el contexto (HTML/Texto de bases) a Gemini y recibir el JSON estructurado con el Scoring.


## Fase 4: Frontend y Pipeline de Gestión
Objetivo: Interfaz funcional para el usuario.
1. Scaffold React: Iniciar Vite + Tailwind.
2. Dashboard de Licitaciones: Vista de lista con filtros y estados (Analizadas, Favoritas, Archivadas).
3. Detalle y Acciones: Visualización del análisis de IA y gestión de hitos (Bases leídas, oferta enviada).
4. Polling de Tareas: Implementar feedback visual para el progreso de Celery.


## Fase 5: Analytics y Cierre
1. Módulo de Resultados: Interfaz para registrar Ganada/Perdida y montos.
2. Dashboard de KPIs: Gráficos de conversión y pipeline de ventas.
3. Exportación: Generación de reportes PDF.