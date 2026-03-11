import unicodedata
import time
import logging
from datetime import datetime
from core.models import Keyword, Tender
from .mercado_publico import MercadoPublicoService

logger = logging.getLogger(__name__)

def normalize_text(text):
    if not text:
        return ""
    text = str(text).lower()
    text = unicodedata.normalize('NFD', text)
    text = "".join([c for c in text if unicodedata.category(c) != 'Mn'])
    return text.strip()

class DiscoveryService:
    def __init__(self):
        self.mp_service = MercadoPublicoService()

    def discover_and_save(self, date_str=None):
        start_time = time.perf_counter()
        if not date_str:
            date_str = datetime.now().strftime('%d%m%Y')

        print(f"[*] Iniciando descubrimiento (MODO SECUENCIAL ROBUSTO) para: {date_str}")
        
        # --- PASO 1: Obtener lista base ---
        list_start = time.perf_counter()
        raw_list = self.mp_service.get_tenders_by_date(date_str)
        list_duration = time.perf_counter() - list_start
        
        if not raw_list:
            print(f"[!] No se encontraron licitaciones (Tiempo: {list_duration:.2f}s)")
            return 0, 0

        print(f"[+] Lista base: {len(raw_list)} licitaciones (Tiempo: {list_duration:.2f}s)")

        # --- PREPARAR KEYWORDS ---
        keywords = Keyword.objects.all()
        positive_terms = [normalize_text(k.term) for k in keywords if not k.is_negative]
        negative_terms = [normalize_text(k.term) for k in keywords if k.is_negative]
        print(f"[*] Keywords cargadas: {len(positive_terms)} (+), {len(negative_terms)} (-)")

        total_processed = len(raw_list)
        suspicious_list = []
        pre_discarded_count = 0

        # --- CAPA 1: EL RADAR (Título) + PRE-FILTRO NEGATIVAS ---
        # Este paso es extremadamente rápido y ahorra muchas llamadas a la API
        for item in raw_list:
            title_norm = normalize_text(item.get("Nombre", ""))
            
            # Si el título tiene una palabra negativa, descartamos de inmediato
            has_negative = any(n in title_norm for n in negative_terms)
            if has_negative:
                pre_discarded_count += 1
                continue

            # Si pasa el filtro de positivas (o no hay positivas definidas)
            is_suspicious = any(p in title_norm for p in positive_terms) if positive_terms else True
            if is_suspicious:
                suspicious_list.append(item)

        print(f"[*] Pre-filtrado completado:")
        print(f"    - Descartadas por negativa en título: {pre_discarded_count}")
        print(f"    - Sospechosas a procesar detalle: {len(suspicious_list)}")

        saved_count = 0
        updated_count = 0
        discarded_detail_count = 0
        detail_times = []

        # --- CAPA 2: LA LUPA (Procesamiento Secuencial) ---
        for i, item in enumerate(suspicious_list, 1):
            mp_id = item.get("CodigoExterno")
            title = item.get("Nombre", "")
            title_norm = normalize_text(title)

            # Pausa educada entre peticiones (0.5s)
            time.sleep(0.5)

            detail_start = time.perf_counter()
            detail = self.mp_service.get_tender_detail(mp_id)
            detail_duration = time.perf_counter() - detail_start
            detail_times.append(detail_duration)

            if not detail:
                print(f"    [{i}/{len(suspicious_list)}] [!] FALLO PERSISTENTE API: {mp_id}")
                continue

            description = normalize_text(detail.get("Descripcion", ""))
            
            categories_text = ""
            items_list = detail.get("Items", {}).get("Listado", [])
            if isinstance(items_list, list):
                for it in items_list:
                    categories_text += " " + it.get("Categoria", "")
            
            categories_norm = normalize_text(categories_text)
            full_text_norm = f"{title_norm} {description} {categories_norm}"

            match_positive = any(p in full_text_norm for p in positive_terms) if positive_terms else True
            is_excluded = any(n in full_text_norm for n in negative_terms)

            if match_positive and not is_excluded:
                tender, created = Tender.objects.update_or_create(
                    mp_id=mp_id,
                    defaults={
                        "title": title,
                        "raw_api_data": detail,
                    }
                )
                if created:
                    saved_count += 1
                    print(f"    [{i}/{len(suspicious_list)}] [V] NUEVA: {mp_id} ({detail_duration:.2f}s)")
                else:
                    updated_count += 1
                    print(f"    [{i}/{len(suspicious_list)}] [~] ACTUALIZADA: {mp_id} ({detail_duration:.2f}s)")
            else:
                discarded_detail_count += 1
                # No imprimimos descartadas para no saturar la consola

        total_duration = time.perf_counter() - start_time
        avg_detail_time = sum(detail_times) / len(detail_times) if detail_times else 0

        print("\n" + "="*50)
        print(f"RESUMEN FINAL (MODO ROBUSTO - {date_str})")
        print(f"Total en Mercado Público: {total_processed}")
        print(f"Descartadas por Título:   {pre_discarded_count}")
        print(f"Consultas de Detalle:     {len(suspicious_list)}")
        print(f"Nuevas Guardadas:         {saved_count}")
        print(f"Actualizadas:             {updated_count}")
        print(f"Descartadas por Detalle:  {discarded_detail_count}")
        print(f"TIEMPO TOTAL:             {total_duration:.2f}s")
        if detail_times:
            print(f"Promedio API:             {avg_detail_time:.2f}s por detalle")
        print("="*50 + "\n")

        return total_processed, saved_count + updated_count
