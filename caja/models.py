from datetime import datetime, time
from decimal import Decimal
from django.db import models
from django.utils import timezone
from pedidos.models import Pedido
from usuarios.models import Usuario

class CierreCaja(models.Model):
    TURNOS = (
        ('MAÑANA', 'Mañana (8am-3pm)'),
        ('TARDE', 'Tarde (3pm-12am)')
    )
    ESTADOS = (
        ('PENDIENTE_VERIFICACION', 'Pendiente Verificación'), # Generado automáticamente
        ('CERRADO', 'Cerrado Definitivamente'),
    )
    
    mozo = models.ForeignKey(Usuario, on_delete=models.PROTECT, limit_choices_to={'rol': 'mozo'})
    fecha = models.DateField()
    turno = models.CharField(max_length=10, choices=TURNOS)
    estado = models.CharField(max_length=25, choices=ESTADOS, default='PENDIENTE_VERIFICACION')
    
    # Totales del sistema
    total_menu_sistema = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_carta_sistema = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_otros_sistema = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_sistema = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Totales físicos (los ingresa el administrador/mozo después)
    efectivo_reportado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tarjetas_reportadas = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    otros_medios = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    diferencia = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Cierre de Caja'
        verbose_name_plural = 'Cierres de Caja'
        ordering = ['-fecha', '-creado_en']
        unique_together = ('mozo', 'fecha', 'turno') # Evita duplicados automáticos

    def __str__(self):
        return f"Cierre Aut. #{self.id} - {self.mozo.username} - {self.turno} ({self.fecha})"

    @classmethod
    def generar_cierres_automaticos(cls, turno_a_cerrar, fecha_cierre):
        """
        Este método será llamado por la tarea programada (Cron/Celery).
        Busca a todos los mozos que tuvieron pedidos en el turno y les genera su cierre.
        """
        mozos_activos = Pedido.objects.filter(
            fecha_hora__date=fecha_cierre,
            turno=turno_a_cerrar,
            estado='PAGADO'
        ).values_list('mozo', flat=True).distinct()

        cierres_creados = []
        for mozo_id in mozos_activos:
            mozo = Usuario.objects.get(id=mozo_id)            
            cierre, creado = cls.objects.get_or_create(
                mozo=mozo,
                fecha=fecha_cierre,
                turno=turno_a_cerrar,
                defaults={'estado': 'PENDIENTE_VERIFICACION'}
            )
            
            # Calcular los totales del sistema inmediatamente
            cierre.calcular_totales_sistema()
            cierres_creados.append(cierre)
            
        return cierres_creados
    def calcular_totales_sistema(self):
        """Tu lógica matemática actual (reducida aquí por espacio, mantenla igual)"""
        fecha_inicio = timezone.make_aware(datetime.combine(self.fecha, time.min))
        fecha_fin = timezone.make_aware(datetime.combine(self.fecha, time.max))

        pedidos = Pedido.objects.filter(mozo=self.mozo, estado='PAGADO')
        pedidos = [
            p for p in pedidos
            if ((p.fecha_pago and fecha_inicio <= p.fecha_pago <= fecha_fin) or
                (not p.fecha_pago and fecha_inicio <= p.fecha_hora <= fecha_fin)) 
            and p.turno == self.turno
        ]

        total_menu = total_carta = total_otros = Decimal('0.00')
        for pedido in pedidos:
            for detalle in pedido.detalles.all():
                subtotal = detalle.subtotal or Decimal('0.00')
                if getattr(detalle, 'plato', None):
                    if (getattr(detalle.plato, 'tipo', '') or '').upper() == 'MENU': total_menu += subtotal
                    else: total_carta += subtotal
                elif getattr(detalle, 'producto', None):
                    if getattr(detalle.producto, 'tipo', '').upper() == 'MENU': total_menu += subtotal
                    else: total_otros += subtotal
                else:
                    total_otros += subtotal

        self.total_menu_sistema = total_menu
        self.total_carta_sistema = total_carta
        self.total_otros_sistema = total_otros
        self.total_sistema = total_menu + total_carta + total_otros
        self.save()

    def procesar_cuadre_fisico(self, efectivo, tarjetas, otros, observaciones=''):
        """Paso final donde el administrador cuenta el dinero real y cierra la auditoría"""
        self.efectivo_reportado = efectivo
        self.tarjetas_reportadas = tarjetas
        self.otros_medios = otros
        self.observaciones = observaciones
        
        total_fisico = (efectivo or 0) + (tarjetas or 0) + (otros or 0)
        self.diferencia = total_fisico - self.total_sistema
        self.estado = 'CERRADO'
        self.cerrado_en = timezone.now()
        self.save()