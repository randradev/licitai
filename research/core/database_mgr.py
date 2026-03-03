# -*- coding: utf-8 -*-
"""
Módulo: Gestor de Persistencia (DatabaseManager)
-----------------------------------------------
Este módulo centraliza la lógica de interacción con la base de datos SQLite.
Implementa el patrón Data Access Object (DAO) para desacoplar la lógica de 
negocio de los detalles de almacenamiento.

Responsabilidades:
1. Garantizar la integridad estructural del esquema de datos.
2. Gestionar el ciclo de vida de las conexiones mediante gestores de contexto.
3. Almacenar perfiles de usuario y resultados del análisis de IA.
"""

import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime

class DatabaseManager:
    """
    Clase encargada de la persistencia de datos del sistema LicitAI.
    
    Centraliza las interacciones con SQLite para mantener el resto del sistema 
    desacoplado de la base de datos.
    """

    def __init__(self, db_path="data/mp_database.db"):
        """
        Inicializar la clase y garantizar la existencia del directorio base.

        Args:
            db_path (str): Ruta al archivo de base de datos SQLite.
        """
        self.db_path = db_path
        # Asegurar que la carpeta 'data/' exista antes de intentar crear la DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """
        Gestionar la conexión a la base de datos mediante un Context Manager.
        
        Garantiza que la conexión se cierre automáticamente tras completar 
        la operación, evitando bloqueos (deadlocks) o corrupción de archivos.

        Yields:
            sqlite3.Connection: Objeto de conexión configurado con Row Factory.
        """
        conn = sqlite3.connect(self.db_path)
        # Configurar Row Factory para permitir acceso a columnas por nombre
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """
        Inicializar las tablas base siguiendo el modelo de datos relacional.
        
        Define las entidades de Perfil de Usuario (Single-tenant) y Licitaciones.
        Utiliza restricciones (CHECK, UNIQUE) para garantizar la integridad.
        """
        with self._get_connection() as conn:
            # ENTIDAD 1: PERFIL DE USUARIO
            # El CHECK (id = 1) garantiza un único perfil activo en el sistema.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS perfil_usuario (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    keywords_pos TEXT,   -- Palabras clave de inclusión
                    keywords_neg TEXT,   -- Filtros de exclusión (ruido)
                    regiones TEXT,       -- Filtros geográficos
                    bio_estrategica TEXT -- Contexto del negocio para el modelo LLM
                )
            """)

            # ENTIDAD 2: LICITACIÓN
            # Almacena el ciclo de vida completo: desde el descubrimiento hasta el análisis de IA.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS licitaciones (
                    id_externo TEXT PRIMARY KEY, -- ID único de Mercado Público
                    titulo TEXT NOT NULL,
                    organismo TEXT,
                    fecha_cierre TEXT,
                    fecha_publicacion TEXT,      -- Capturada dinámicamente desde la ficha
                    reclamo_pago TEXT,           -- Historial cualitativo del organismo
                    link TEXT,
                    descripcion_pro TEXT,        -- Cuerpo extraído para análisis semántico
                    score_ia INTEGER,            -- Priorización numérica (0-100)
                    analisis_ia_json TEXT,       -- Estructura JSON con riesgos y veredicto
                    estado TEXT DEFAULT 'pendiente', -- Ciclo: pendiente -> extraido -> analizado
                    motivo_archivo TEXT,         -- Feedback de la IA en caso de descarte
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    # ===================================================================
    # GESTIÓN DE PERFIL (Configuración de Negocio)
    # ===================================================================

    def guardar_perfil(self, keywords_pos, keywords_neg, regiones, bio):
        """
        Crear o actualizar el perfil estratégico del usuario.
        """
        query = """
            INSERT OR REPLACE INTO perfil_usuario (id, keywords_pos, keywords_neg, regiones, bio_estrategica)
            VALUES (1, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            conn.execute(query, (keywords_pos, keywords_neg, regiones, bio))
            conn.commit()

    def obtener_perfil(self):
        """
        Recuperar la configuración del perfil para el Scraper y la IA.

        Returns:
            dict: Datos del perfil o None si no se ha configurado.
        """
        with self._get_connection() as conn:
            res = conn.execute("SELECT * FROM perfil_usuario WHERE id = 1").fetchone()
            return dict(res) if res else None

    # ===================================================================
    # GESTIÓN DE LICITACIONES (Operaciones CRUD)
    # ===================================================================
    
    def guardar_licitacion(self, data):
        """
        Registrar una licitación descubierta mediante la API.
        Evita duplicados mediante la cláusula INSERT OR IGNORE.
        """
        f_pub = data.get('fecha_publicacion', 'Procesando...')
        
        query = """
            INSERT OR IGNORE INTO licitaciones 
            (id_externo, titulo, organismo, fecha_cierre, fecha_publicacion)
            VALUES (?, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            conn.execute(query, (
                data['id_externo'],
                data['titulo'],
                data.get('organismo', 'Procesando...'),
                data['fecha_cierre'],
                f_pub
            ))
            conn.commit()

    def actualizar_detalle_profundo(self, id_externo, link, texto_pro):
        """
        Actualizar la licitación con datos extendidos capturados del navegador.
        
        Cambia el estado de la licitación a 'extraido' para indicar que está 
        lista para el análisis de IA.
        """
        query = "UPDATE licitaciones SET link = ?, descripcion_pro = ?, estado = 'extraido' WHERE id_externo = ?"
        with self._get_connection() as conn:
            conn.execute(query, (link, texto_pro, id_externo))
            conn.commit()

    def obtener_licitaciones(self, estado=None):
        """
        Recuperar el conjunto de licitaciones filtrado por estado.

        Args:
            estado (str, optional): Estado de la licitación (pendiente, analizado, etc.)

        Returns:
            list: Lista de diccionarios representando las licitaciones.
        """
        query = "SELECT * FROM licitaciones"
        params = ()
        
        if estado:
            query += " WHERE estado = ?"
            params = (estado,)

        # Ordenar por relevancia temporal y técnica
        query += " ORDER BY fecha_publicacion DESC, score_ia DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        
    def existe_licitacion(self, id_externo):
        """
        Verificar la existencia de un ID externo para evitar reprocesamiento.
        """
        with self._get_connection() as conn:
            res = conn.execute("SELECT 1 FROM licitaciones WHERE id_externo = ?", (id_externo,)).fetchone()
            return res is not None

    def guardar_analisis_ia(self, id_externo, score, analisis_json, motivo=None):
        """
        Persistir los resultados generados por el modelo de IA.
        
        Args:
            id_externo (str): ID de la licitación.
            score (int): Puntaje de idoneidad.
            analisis_json (dict): Estructura de riesgos y oportunidades.
            motivo (str, optional): Justificación de archivo en scores bajos.
        """
        query = """
            UPDATE licitaciones 
            SET score_ia = ?, analisis_ia_json = ?, motivo_archivo = ?, estado = 'analizado'
            WHERE id_externo = ?
        """
        with self._get_connection() as conn:
            conn.execute(query, (score, json.dumps(analisis_json), motivo, id_externo))
            conn.commit()

    def cambiar_estado(self, id_externo, nuevo_estado):
        """
        Actualizar el estado de gestión de una licitación (ej: Favorita, Archivada).
        """
        query = "UPDATE licitaciones SET estado = ? WHERE id_externo = ?"
        with self._get_connection() as conn:
            conn.execute(query, (nuevo_estado, id_externo))
            conn.commit()

    def actualizar_datos_maestros(self, id_externo, titulo=None, organismo=None, fecha_pub=None, reclamo_pago=None):
        """
        Actualizar metadatos oficiales recuperados durante la navegación profunda.
        """
        with self._get_connection() as conn:
            if titulo:
                conn.execute("UPDATE licitaciones SET titulo = ? WHERE id_externo = ?", (titulo, id_externo))
            if organismo:
                conn.execute("UPDATE licitaciones SET organismo = ? WHERE id_externo = ?", (organismo, id_externo))
            if fecha_pub:
                conn.execute("UPDATE licitaciones SET fecha_publicacion = ? WHERE id_externo = ?", (fecha_pub, id_externo))
            if reclamo_pago:
                conn.execute("UPDATE licitaciones SET reclamo_pago = ? WHERE id_externo = ?", (reclamo_pago, id_externo))
            conn.commit()

    def reparar_datos_licitacion(self, id_externo, titulo_ia, organismo_ia, reclamos_ia):
        """
        Corregir información incompleta o con ruido usando inferencia semántica de la IA.
        
        Solo sobrescribe datos si los valores actuales son marcadores de posición 
        o están vacíos, asegurando la calidad de la información en el dashboard.
        """
        query_select = "SELECT titulo, organismo, reclamo_pago FROM licitaciones WHERE id_externo = ?"
        
        with self._get_connection() as conn:
            current = conn.execute(query_select, (id_externo,)).fetchone()
            
            if not current:
                return

            updates = []
            params = []

            # Reparar Título si es ruido o placeholder
            if current['titulo'] in ["Sin título", "Procesando...", ""]:
                updates.append("titulo = ?")
                params.append(titulo_ia)

            # Reparar Organismo
            if current['organismo'] in ["No detectado", "Procesando...", ""]:
                updates.append("organismo = ?")
                params.append(organismo_ia)

            # Reclamo de pago: siempre se actualiza por la precisión de la lectura de IA
            if reclamos_ia:
                updates.append("reclamo_pago = ?")
                params.append(reclamos_ia)

            if updates:
                sql_update = f"UPDATE licitaciones SET {', '.join(updates)} WHERE id_externo = ?"
                params.append(id_externo)
                conn.execute(sql_update, params)
                conn.commit()