from django.db import models
from core.services.encryption import EncryptionService


class GlobalConfig(models.Model):
    """
    Almacena la configuración global del sistema, incluyendo credenciales
    cifradas y balance de créditos para el uso de la API/IA.
    """
    # Ticket de la API de Mercado Público cifrado con AES-256.
    api_ticket_encrypted = models.TextField()
    # Balance disponible para operaciones de IA.
    credits_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def __str__(self):
        return "Configuración Global"

    def save(self, *args, **kwargs):
        """
        Sobrescribimos el método save para cifrar el ticket automáticamente
        si detectamos que es texto plano.
        """
        if self.api_ticket_encrypted:
            service = EncryptionService()
            try:
                # Intentamos descifrarlo. Si falla, asumimos que es texto plano.
                service.decrypt(self.api_ticket_encrypted)
            except Exception:
                # Si lanza error, es que no está cifrado. ¡Lo ciframos ahora!
                self.api_ticket_encrypted = service.encrypt(self.api_ticket_encrypted)
        
        super().save(*args, **kwargs)

    def get_api_ticket(self):
        """
        Devuelve el ticket descifrado para su uso en la API.
        """
        if not self.api_ticket_encrypted:
            return ""
        service = EncryptionService()
        return service.decrypt(self.api_ticket_encrypted)


class Keyword(models.Model):
    """
    Términos de búsqueda utilizados para filtrar licitaciones.
    Pueden ser positivos (inclusión) o negativos (exclusión).
    """
    # Palabra o frase de búsqueda.
    term = models.CharField(max_length=100)
    # Si es True, la keyword se usa para descartar licitaciones.
    is_negative = models.BooleanField(default=False)

    def __str__(self):
        prefix = "[-]" if self.is_negative else "[+]"
        return f"{prefix} {self.term}"


class Tender(models.Model):
    """
    Representa una licitación capturada desde Mercado Público.
    Contiene la información cruda y metadatos básicos.
    """
    # Identificador único de la licitación en Mercado Público (ID Licitación).
    mp_id = models.CharField(max_length=50, unique=True)
    # Título o nombre del proyecto.
    title = models.CharField(max_length=255)
    # Fecha estimada o real de adjudicación.
    adjudication_date = models.DateTimeField(null=True, blank=True)
    # Datos completos obtenidos desde la API en formato JSON.
    raw_api_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Mostramos el ID y los primeros 50 caracteres del título.
        return f"{self.mp_id} - {self.title[:50]}"


class Attachment(models.Model):
    """
    Documentos adjuntos a una licitación (bases, anexos, aclaraciones).
    """
    # Licitación a la que pertenece este archivo. Relación muchos a uno.
    tender = models.ForeignKey(
        'Tender', 
        on_delete=models.CASCADE, 
        related_name='attachments'
    )
    file_name = models.CharField(max_length=255)
    # URL de descarga del documento.
    url = models.URLField(max_length=500)

    def __str__(self):
        return self.file_name


class Analysis(models.Model):
    """
    Resultados de los análisis realizados por la IA (Gemini).
    Puede ser de nivel 1 (Ficha) o nivel 2 (Bases/Profundo).
    """
    LEVEL_CHOICES = [
        ('SIMPLE', 'Análisis Nivel 1 (Ficha)'),
        ('DEEP', 'Análisis Nivel 2 (Bases)'),
    ]
    # Relación muchos a uno con Tender.
    tender = models.ForeignKey(
        'Tender', 
        on_delete=models.CASCADE, 
        related_name='analyses'
    )
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    # Puntaje de relevancia asignado por la IA (0-100).
    score = models.IntegerField(default=0)
    # Resumen estructurado y hallazgos de la IA en formato JSON.
    result_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Mostramos nivel, score e ID de la licitación.
        return f"{self.level} - Score: {self.score} ({self.tender.mp_id})"


class TenderManagement(models.Model):
    """
    Gestión operativa y seguimiento de una licitación favorita.
    Incluye estados del pipeline, notas y resultados finales.
    """
    STATUS_CHOICES = [
        ('ANALYZED', 'Analizada'),
        ('FAVORITE', 'Favorita'),
        ('ARCHIVED', 'Archivada'),
    ]
    OUTCOME_CHOICES = [
        ('WON', 'Ganada'),
        ('LOST', 'Perdida'),
        ('NOT_PRESENTED', 'No Presentada'),
    ]

    # Relación uno a uno con Tender.
    tender = models.OneToOneField(
        'Tender', 
        on_delete=models.CASCADE, 
        related_name='management'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ANALYZED')

    # Hitos de preparación (Checklist).
    status_bases = models.BooleanField(default=False)
    status_annexes = models.BooleanField(default=False)
    status_sent = models.BooleanField(default=False)

    # Notas tácticas internas.
    internal_notes = models.TextField(blank=True)
    # Resultado de la licitación (Ganada/Perdida).
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, null=True, blank=True)
    # Monto total ofertado.
    bid_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    # Lecciones aprendidas o feedback del proceso.
    feedback_notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # Accedemos de forma segura a mp_id de la licitación relacionada.
        return f"Gestión: {self.tender.mp_id}"
