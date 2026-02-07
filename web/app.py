# -*- coding: utf-8 -*-
"""
Módulo: Interfaz de Usuario (LicitAIWeb)
---------------------------------------
Implementa el dashboard interactivo utilizando Streamlit. 
Este módulo actúa como la capa de presentación, permitiendo al usuario:
1. Configurar su perfil de negocio y criterios de búsqueda.
2. Visualizar y gestionar licitaciones analizadas por la IA.
3. Orquestar manualmente la sincronización con Mercado Público.
"""

import streamlit as st
import json
from datetime import datetime
from core.database_mgr import DatabaseManager

# Configuración global de la página y metadatos del navegador
st.set_page_config(
    page_title="LicitAI - Dashboard",
    page_icon="🤖",
    layout="wide"
)

class LicitAIWeb:
    """
    Clase principal para la gestión y renderizado de la interfaz web.
    
    Encapsula la lógica de visualización y los componentes de interacción 
    con el usuario final.
    """

    def __init__(self):
        """
        Inicializar la conexión con la persistencia de datos.
        """
        self.db = DatabaseManager()

    def _render_pago_badge(self, reclamo_txt):
        """
        Visualizar un indicador de riesgo de pago basado en el historial del organismo.

        Args:
            reclamo_txt (str): Texto descriptivo sobre el comportamiento de pago.
        """
        # Evaluar la presencia de riesgos de pago mediante análisis de cadenas
        if not reclamo_txt or "0" in reclamo_txt or "No informado" in reclamo_txt:
            st.success(f"💳 Pagos: {reclamo_txt}")
        else:
            # Alertar visualmente si se detectan reclamos mayores a cero
            st.warning(f"⚠️ Riesgo Pago: {reclamo_txt}")

    def render_sidebar(self):
        """
        Renderizar la barra lateral con controles de sistema y perfil de negocio.
        """
        st.sidebar.title("⚙️ Panel de Control")
        
        # --- SECCIÓN: SINCRONIZACIÓN ---
        st.sidebar.subheader("🔄 Sincronización")
        if st.sidebar.button("🚀 Buscar y Analizar Hoy", use_container_width=True):
            with st.sidebar.status("Ejecutando proceso...", expanded=True) as status:
                try:
                    # Importación diferida para evitar dependencias circulares
                    from main import ejecutar_pipeline
                    ejecutar_pipeline()
                    status.update(label="Sincronización Exitosa", state="complete")
                    st.toast("Nuevas licitaciones cargadas.")
                    st.rerun()
                except Exception as e:
                    status.update(label="Error en el proceso", state="error")
                    st.error(f"Detalle: {e}")

        st.sidebar.markdown("---")
        
        # --- SECCIÓN: PERFIL DE NEGOCIO ---
        # Recuperar configuración actual para pre-poblar el formulario
        perfil = self.db.obtener_perfil() or {}
        st.sidebar.subheader("🏢 Perfil de Negocio")
        with st.sidebar.form("perfil_form"):
            keywords_pos = st.text_area("Keywords Positivas", perfil.get('keywords_pos', ''))
            keywords_neg = st.text_area("Keywords Negativas", perfil.get('keywords_neg', ''))
            bio = st.text_area("Bio Estratégica (Contexto IA)", perfil.get('bio_estrategica', ''), height=150)
            
            if st.form_submit_button("Guardar Cambios"):
                # Actualizar el modelo de datos con la nueva configuración
                self.db.guardar_perfil(keywords_pos, keywords_neg, "Chile", bio)
                st.sidebar.success("✅ Perfil actualizado")
                st.rerun()

    def dibujar_lista_licitaciones(self, lista, simplificado=False):
        """
        Renderizar la lista de licitaciones agrupadas cronológicamente.

        Args:
            lista (list): Colección de licitaciones a visualizar.
            simplificado (bool): Si es True, omite detalles extensos de IA (útil para archivos).
        """
        if not lista:
            st.info("No hay licitaciones para mostrar.")
            return

        # Agrupar registros por fecha de publicación para facilitar la lectura
        grupos = {}
        for l in lista:
            f_str = l.get('fecha_publicacion') or "Sin fecha oficial"
            if f_str not in grupos:
                grupos[f_str] = []
            grupos[f_str].append(l)

        # Renderizar grupos en orden descendente (más recientes primero)
        for fecha in sorted(grupos.keys(), reverse=True):
            st.markdown(f"#### 📅 Publicadas el {fecha}")
            
            for l in grupos[fecha]:
                score = l.get('score_ia', 0)
                
                # --- RESOLUCIÓN DINÁMICA DE TÍTULO ---
                # Priorizar el título recuperado por IA sobre el título de la API
                titulo_final = None
                if l['analisis_ia_json']:
                    try:
                        data_ia = json.loads(l['analisis_ia_json'])
                        titulo_final = data_ia.get('titulo_recuperado')
                    except:
                        pass
                
                if not titulo_final:
                    titulo_final = l['titulo'] if l['titulo'] and l['titulo'] not in ["Sin título", "Procesando..."] else None
                
                titulo_display_text = titulo_final if titulo_final else f"Licitación {l['id_externo']}"
                
                # Truncar título para mantener la UI limpia
                titulo_header = (titulo_display_text[:85] + '...') if len(titulo_display_text) > 85 else titulo_display_text
                color = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
                
                with st.expander(f"{color} {score}/10 - {titulo_header}"):
                    c1, c2 = st.columns([2.5, 1])
                    with c1:
                        organismo_display = l['organismo'] if l['organismo'] and str(l['organismo']) != "None" else "Organismo no detectado"
                        st.write(f"**🏢 {organismo_display}**")
                        
                        self._render_pago_badge(l.get('reclamo_pago'))
                        st.caption(f"🕒 **Cierre:** {l['fecha_cierre']} | **ID:** {l['id_externo']}")
                        
                        # Mostrar el análisis semántico si existe
                        if l['analisis_ia_json']:
                            an = json.loads(l['analisis_ia_json'])
                            st.info(f"**🧠 Veredicto:** {an.get('veredicto')}")
                            if not simplificado:
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.markdown("**✅ Fortalezas:**")
                                    for p in an.get('puntos_criticos', [])[:3]: st.caption(f"• {p}")
                                with col_b:
                                    st.markdown("**⚠️ Riesgos:**")
                                    for r in an.get('riesgos', [])[:3]: st.caption(f"• {r}")
                        
                        st.link_button("🌐 Ver en Mercado Público", l['link'] or "#")
                    
                    with c2:
                        st.metric("Match IA", f"{score}/10")
                        # Controles de estado de la licitación
                        if l['estado'] == 'analizado':
                            if st.button("⭐ Favorita", key=f"fav_{l['id_externo']}", use_container_width=True):
                                self.db.cambiar_estado(l['id_externo'], 'favorita'); st.rerun()
                            if st.button("📁 Archivar", key=f"arc_{l['id_externo']}", use_container_width=True):
                                self.db.cambiar_estado(l['id_externo'], 'archivada'); st.rerun()
                        else:
                            if st.button("🔄 Re-evaluar", key=f"re_{l['id_externo']}", use_container_width=True):
                                self.db.cambiar_estado(l['id_externo'], 'analizado'); st.rerun()
            st.divider()

    def dibujar_favoritas_detallado(self, lista):
        """
        Renderizar la vista extendida para licitaciones marcadas como favoritas.
        Ordena por puntaje estratégico de IA.
        """
        lista_ordenada = sorted(lista, key=lambda x: x.get('score_ia', 0), reverse=True)

        for l in lista_ordenada:
            score = l.get('score_ia', 0)
            titulo = l['titulo'] or f"Licitación {l['id_externo']}"
            
            with st.container(border=True):
                c_head1, c_head2 = st.columns([3, 1])
                with c_head1:
                    st.subheader(f"🌟 {titulo}")
                with c_head2:
                    st.metric("Puntaje Estratégico", f"{score}/10")

                c1, c2, c3 = st.columns([1.2, 1.8, 1])
                
                with c1:
                    st.markdown("##### 📋 Ficha Técnica")
                    st.write(f"**Organismo:**\n{l['organismo']}")
                    self._render_pago_badge(l.get('reclamo_pago'))
                    st.write(f"**Publicación:** {l['fecha_publicacion']}")
                    st.write(f"**Cierre:** {l['fecha_cierre']}")
                    st.link_button("🚀 Abrir en Portal", l['link'] or "#", use_container_width=True)
                    if st.button("⬅️ Quitar de Favoritas", key=f"back_{l['id_externo']}", use_container_width=True):
                        self.db.cambiar_estado(l['id_externo'], 'analizado'); st.rerun()

                with c2:
                    st.markdown("##### 🧠 Análisis de la IA")
                    if l['analisis_ia_json']:
                        an = json.loads(l['analisis_ia_json'])
                        st.success(f"**Veredicto:** {an.get('veredicto')}")
                        st.markdown("**Puntos Clave:**")
                        for p in an.get('puntos_criticos', []): st.write(f"🔹 {p}")
                        with st.expander("Ver Riesgos Detectados"):
                            for r in an.get('riesgos', []): st.write(f"🔸 {r}")

                with c3:
                    # Funcionalidades adicionales para gestión operativa
                    st.markdown("##### 📝 Gestión")
                    st.checkbox("Bases leídas", key=f"b1_{l['id_externo']}")
                    st.checkbox("Anexos preparados", key=f"b2_{l['id_externo']}")
                    st.text_area("Notas internas:", placeholder="Ej: Costos revisados...", key=f"txt_{l['id_externo']}")

    def run(self):
        """
        Punto de entrada principal para renderizar la aplicación.
        """
        self.render_sidebar()
        st.title("🤖 LicitAI: Radar Inteligente")
        
        # Organización de la vista por pestañas de estado
        tab1, tab2, tab3 = st.tabs(["🎯 Analizadas", "🌟 Favoritas", "📁 Archivadas"])
        
        with tab1:
            licitaciones = self.db.obtener_licitaciones(estado='analizado')
            if not licitaciones: 
                st.info("No hay nuevas licitaciones analizadas hoy.")
            else: 
                self.dibujar_lista_licitaciones(licitaciones)

        with tab2:
            favs = self.db.obtener_licitaciones(estado='favorita')
            if not favs: 
                st.info("No tienes favoritas seleccionadas aún.")
            else: 
                self.dibujar_favoritas_detallado(favs)

        with tab3:
            archived = self.db.obtener_licitaciones(estado='archivada')
            if not archived: 
                st.info("El historial de archivadas está vacío.")
            else: 
                self.dibujar_lista_licitaciones(archived, simplificado=True)

# --- INVOCACIÓN DEL PUNTO DE ENTRADA ---
if __name__ == "__main__":
    app = LicitAIWeb()
    app.run()