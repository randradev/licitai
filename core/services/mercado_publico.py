import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.conf import settings
from core.models import GlobalConfig

class MercadoPublicoService:
    """
    Servicio robusto para interactuar con la API de Mercado Público.
    Incluye lógica de reintentos y manejo de sesiones.
    """
    BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"

    def __init__(self):
        config = GlobalConfig.objects.first()
        if not config:
            raise ValueError("No se encontró la configuración global.")
        
        self.ticket = config.get_api_ticket()
        
        # Configuración de Reintentos (Retry Strategy)
        # Reintentará 5 veces ante errores de servidor.
        # El backoff_factor de 2 hará esperas de: 2s, 4s, 8s, 16s, 32s.
        retry_strategy = Retry(
            total=5,
            backoff_factor=2, 
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_tenders_by_date(self, date_str):
        url = f"{self.BASE_URL}/licitaciones.json"
        params = {"fecha": date_str, "ticket": self.ticket}
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("Listado", [])
        except Exception as e:
            print(f"Error masivo por fecha {date_str}: {e}")
            return []

    def get_tender_detail(self, code):
        url = f"{self.BASE_URL}/licitaciones.json"
        params = {"codigo": code, "ticket": self.ticket}
        try:
            # Hacemos la petición a través de la sesión con reintentos
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            listado = data.get("Listado", [])
            return listado[0] if listado else None
        except Exception as e:
            # Si tras los reintentos sigue fallando, registramos y saltamos
            print(f"Error persistente en detalle {code}: {e}")
            return None
