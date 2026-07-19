from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from .models import CierreCaja
from pedidos.models import Pedido
from datetime import datetime, time
from django.utils import timezone
from decimal import Decimal

class CierreCajaListView(LoginRequiredMixin, ListView):
    model = CierreCaja
    template_name = 'caja/cierre_list.html'
    context_object_name = 'cierres'

class CierreCajaDetailView(LoginRequiredMixin, DetailView):
    model = CierreCaja
    template_name = 'caja/cierre_detail.html'
    context_object_name = 'cierre'  # Esto corrige definitivamente el error NoReverseMatch

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cierre = self.object
        
        fecha_inicio = timezone.make_aware(datetime.combine(cierre.fecha, time.min))
        fecha_fin = timezone.make_aware(datetime.combine(cierre.fecha, time.max))

        pedidos = Pedido.objects.filter(
            mozo=cierre.mozo,
            fecha_hora__range=(fecha_inicio, fecha_fin),
            turno=cierre.turno,
            estado='PAGADO'
        ).select_related('mesa').prefetch_related('detalles__plato', 'detalles__producto')

        context.update({
            'pedidos': pedidos,
            'pendiente_cuadre': cierre.estado == 'PENDIENTE_VERIFICACION',
            'detalle_items': self._obtener_detalle_items(pedidos),
            'total_general': cierre.total_sistema 
        })
        return context

    def post(self, request, *args, **kwargs):
        """Procesa la rendición física directamente mediante una petición POST desde el detalle"""
        cierre = self.get_object()
        
        efectivo = Decimal(request.POST.get('efectivo_reportado') or '0.00')
        tarjetas = Decimal(request.POST.get('tarjetas_reportadas') or '0.00')
        otros = Decimal(request.POST.get('otros_medios') or '0.00')
        observaciones = request.POST.get('observaciones', '')

        cierre.procesar_cuadre_fisico(
            efectivo=efectivo,
            tarjetas=tarjetas,
            otros=otros,
            observaciones=observaciones
        )
        
        messages.success(request, f'Rendición procesada. Diferencia calculada: S/ {cierre.diferencia}')
        return redirect('caja:cierre_detail', pk=cierre.pk)

    def _obtener_detalle_items(self, pedidos):
        detalles = []
        for pedido in pedidos:
            for detalle in pedido.detalles.all():
                nombre_item = detalle.plato.nombre if detalle.plato else detalle.producto.nombre
                tipo_item = detalle.plato.get_tipo_display() if detalle.plato else "Producto"
                detalles.append({
                    'item': nombre_item,
                    'tipo': tipo_item,
                    'cantidad': detalle.cantidad,
                    'subtotal': detalle.subtotal
                })
        return detalles