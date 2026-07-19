from datetime import timedelta
from django.core.management.base import BaseCommand
from caja.models import CierreCaja
from django.utils import timezone

class Command(BaseCommand):
    help = 'Cierra el turno correspondiente de forma automatizada'

    def handle(self, *args, **options):
        ahora = timezone.localtime(timezone.now())
        hora = ahora.hour

        if 11 <= hora <= 16:
            turno = 'MAÑANA'
            fecha_cierre = ahora.date()
        else:
            turno = 'TARDE'
            # Si es medianoche (00:00), los pedidos pertenecen al día que acaba de terminar
            fecha_cierre = (ahora - timedelta(days=1)).date()

        self.stdout.write(f"Iniciando cierre para {turno} de la fecha {fecha_cierre}")
        
        # Llama al método que acepta la fecha calculada
        cierres = CierreCaja.generar_cierres_automaticos(turno, fecha_cierre)
        self.stdout.write(self.style.SUCCESS(f"Éxito. Se procesaron {len(cierres)} cierres."))