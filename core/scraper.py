# -*- coding: utf-8 -*-
"""
Módulo: Extractor de Licitaciones (LicitacionScraper)
---------------------------------------------------
Este módulo implementa el pipeline de descubrimiento y captura de datos 
desde el portal Mercado Público. 

Responsabilidades:
1. Consultar la API oficial para el descubrimiento de nuevas oportunidades.
2. Filtrar resultados basados en el perfil de búsqueda del usuario.
3. Ejecutar la navegación automatizada (Selenium) para la extracción de 
   detalles técnicos y cláusulas desde la ficha profunda.
"""

import requests
import os
import time
import re
from datetime import datetime
from dotenv import load_dotenv
from core.database_mgr import DatabaseManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Cargar configuración de entorno para acceso a API y tickets
load_dotenv()

class LicitacionScraper:
    """
    Clase encargada del descubrimiento y extracción de datos.
    
    Centraliza la comunicación con la API de Mercado Público y gestiona el 
    ciclo de vida del navegador automatizado para el scraping de fichas técnicas.
    """

    def __init__(self, db_manager):
        """
        Inicializar el scraper e inyectar la dependencia de persistencia.

        Args:
            db_manager (DatabaseManager): Instancia para verificar existencia 
                                          y perfiles de búsqueda.
        """
        self.db = db_manager
        self.api_ticket = os.getenv("MP_TICKET")
        self.base_url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"

    # -------------------------------------------------------------------
    # PARTE 1: DESCUBRIMIENTO GENERAL (API REST)
    # -------------------------------------------------------------------

    def obtener_keywords_busqueda(self):
        """
        Consultar las palabras clave configuradas en el perfil del usuario.

        Returns:
            list: Lista de términos de búsqueda normalizados.
        """
        perfil = self.db.obtener_perfil()
        if not perfil or not perfil['keywords_pos']:
            print("⚠️ No hay palabras clave configuradas en el perfil.")
            return []
        
        # Limpiar espacios y segmentar la cadena de texto en una lista ejecutable
        return [k.strip() for k in perfil['keywords_pos'].split(',')]
    
    def descubrir_licitaciones_del_dia(self):
        """
        Consultar la API masiva para obtener todas las licitaciones de la fecha actual.

        Returns:
            list: Listado bruto de licitaciones encontradas.
        """
        if not self.api_ticket:
            print("❌ Error: MP_TICKET no encontrado en .env")
            return []
        
        # Formatear la fecha según el estándar requerido por la API (DDMMAAAA)
        fecha_hoy = datetime.now().strftime("%d%m%Y")
        parametros = {
            'fecha': fecha_hoy,
            'ticket': self.api_ticket
        }

        try:
            print(f"🔍 Buscando licitaciones publicadas hoy: {fecha_hoy}...")
            respuesta = requests.get(self.base_url, params=parametros)

            if respuesta.status_code == 200:
                datos = respuesta.json()
                return datos.get('Listado', [])
            else:
                print(f"❌ Error en la API: {respuesta.status_code} - {respuesta.reason}")
                return []
        except Exception as e:
            print(f"❌ Error de conexión al intentar descubrir: {e}")
            return []
        
    def filtrar_licitaciones_relevantes(self, lista_bruta):
        """
        Aplicar criterios de filtrado técnico y estratégico sobre el listado bruto.
        
        Criterios:
        - Estado 5: Únicamente licitaciones en estado 'Publicada'.
        - Keywords: Coincidencia en el título con el rubro del usuario.
        - Unicidad: Exclusión de registros ya existentes en la base de datos.

        Args:
            lista_bruta (list): Listado original de la API.

        Returns:
            list: Licitaciones aptas para procesamiento profundo.
        """
        keywords = self.obtener_keywords_busqueda()
        licitaciones_interesantes = []
        
        # Estado 5 representa 'Publicada', fase activa para participar
        ESTADOS_VIGENTES = [5] 

        print(f"🧐 Filtrando {len(lista_bruta)} licitaciones por estado y relevancia...")

        for licit in lista_bruta:
            nombre_licit = (licit.get('Nombre') or "").lower()
            codigo = licit.get('CodigoExterno')
            estado = licit.get('CodigoEstado')

            # Validación de triple factor para optimizar recursos de scraping
            if estado in ESTADOS_VIGENTES:
                if any(key.lower() in nombre_licit for key in keywords):
                    if not self.db.existe_licitacion(codigo):
                        licitaciones_interesantes.append(licit)
            
        print(f"🎯 Filtro completado: {len(licitaciones_interesantes)} licitaciones aptas.")
        return licitaciones_interesantes
    
    def ejecutar_pipeline_descubrimiento(self):
        """
        Orquestar el flujo de descubrimiento y pre-filtrado.

        Returns:
            list: Candidatos finales para el análisis profundo.
        """
        listado_total = self.descubrir_licitaciones_del_dia()

        if not listado_total:
            print("👀 No se encontraron licitaciones nuevas en el listado general.")
            return []
        
        print(f"📋 Total de licitaciones publicadas hoy: {len(listado_total)}")
        finales = self.filtrar_licitaciones_relevantes(listado_total)
        return finales
    
    # -------------------------------------------------------------------
    # PARTE 2: EXTRACCIÓN PROFUNDA (SELENIUM)
    # -------------------------------------------------------------------

    def extraer_detalle_licitacion(self, codigo_licitacion):
        """
        Navegar al portal Mercado Público para capturar el contenido técnico detallado.
        
        Utiliza técnicas de automatización para superar iframes complejos y 
        pop-ups del portal oficial.

        Args:
            codigo_licitacion (str): Código externo (ej: 1234-56-LP24).

        Returns:
            dict: Diccionario con link, descripción técnica y metadatos capturados.
        """
        url_home = "https://www.mercadopublico.cl"
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("window-size=1920,1080")
        # Simulación de User-Agent para minimizar bloqueos por fingerprinting
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        wait = WebDriverWait(driver, 25) 
        
        resultado = {
            "link": "No disponible",
            "descripcion_pro": "No se pudo extraer el detalle técnico.",
            "organismo": "No detectado",
            "titulo_oficial": "Sin título",
            "fecha_publicacion": datetime.now().strftime("%Y-%m-%d"),
            "reclamo_pago": "No informado"
        }

        try:
            driver.get(url_home)

            # Gestión proactiva de alertas/pop-ups del portal
            try:
                WebDriverWait(driver, 3).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                print(f"⚠️ Alerta de portal detectada ('{alert.text}'), cerrando...")
                alert.accept()
                time.sleep(1)
                driver.refresh()
            except:
                pass
            
            # Ejecutar búsqueda por código externo
            search_input = wait.until(EC.visibility_of_element_located((By.ID, "txtBuscar")))
            search_input.clear()
            search_input.send_keys(codigo_licitacion)
            
            # Clic mediante JavaScript para asegurar interacción en elementos superpuestos
            try:
                boton_buscar = wait.until(EC.element_to_be_clickable((By.ID, "btnBuscar")))
                driver.execute_script("arguments[0].click();", boton_buscar)
            except:
                driver.execute_script("document.getElementById('btnBuscar').click();")

            # Salto al iframe de resultados para acceder al DOM dinámico
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "form-iframe")))

            # Localizar el enlace de la licitación específica mediante el atributo onclick
            selector_xpath = f"//a[contains(@onclick, '{codigo_licitacion}')]"
            enlace_elem = wait.until(EC.presence_of_element_located((By.XPATH, selector_xpath)))
            onclick_txt = enlace_elem.get_attribute("onclick")
            url_match = re.search(r"'(http.*?)'", onclick_txt)
            
            if url_match:
                resultado["link"] = url_match.group(1)
                
                # Navegar a la ficha técnica final
                driver.get(resultado["link"])
                
                # Sincronización: Esperar carga real del contenido textual
                wait.until(lambda d: d.find_element(By.TAG_NAME, "body").text.strip() != "")
                time.sleep(4) 
                
                # Extracción robusta: Captura del texto en el nivel principal y sub-iframes
                driver.switch_to.default_content()
                texto_final = driver.execute_script("return document.body.innerText;")
                
                # Si la captura es insuficiente, iterar sobre iframes internos (anidamiento profundo)
                if len(texto_final.strip()) < 1000:
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for i in range(len(iframes)):
                        try:
                            driver.switch_to.default_content()
                            driver.switch_to.frame(i)
                            texto_final += "\n" + driver.execute_script("return document.body.innerText;")
                        except:
                            continue
                
                resultado["descripcion_pro"] = texto_final
                
                # Análisis preventivo: Rescatar metadatos si están presentes en texto plano
                if "Organismo" in texto_final:
                    match_org = re.search(r"Nombre del Organismo\s*:\s*(.*)", texto_final)
                    if match_org: resultado["organismo"] = match_org.group(1).strip()

            return resultado
        
        except Exception as e:
            print(f"⚠️ Error en extracción de {codigo_licitacion}: {str(e)}")
            return resultado
        finally:
            driver.quit()