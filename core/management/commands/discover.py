from django.core.management.base import BaseCommand
from core.services.discovery import DiscoveryService

class Command(BaseCommand):
    help = 'Ejecuta el descubrimiento de licitaciones desde Mercado Público'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date', 
            type=str, 
            help='Fecha en formato DDMMAAAA (ej: 06032026). Si no se indica, usa hoy.'
        )

    def handle(self, *args, **options):
        date_str = options['date']
        self.stdout.write(self.style.NOTICE(f'Iniciando descubrimiento para: {date_str or "Hoy"}...'))
        
        try:
            service = DiscoveryService()
            total, saved = service.discover_and_save(date_str)
            
            success_msg = (
                f"Proceso completado con éxito.\n"
                f"- Licitaciones procesadas: {total}\n"
                f"- Licitaciones nuevas/actualizadas: {saved}"
            )
            self.stdout.write(self.style.SUCCESS(success_msg))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error en el proceso: {str(e)}"))
