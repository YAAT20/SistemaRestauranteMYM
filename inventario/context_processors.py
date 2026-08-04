from django.db.models import F
from .models import Producto

def notificaciones_inventario(request):
    if request.user.is_authenticated:
        # Cuenta cuántos productos activos están agotados o en stock bajo
        productos_criticos_count = Producto.objects.filter(activo=True).extra(
            where=["stock <= punto_pedido"]
        ).count()
        
        # Lista rápida para mostrar en un menú desplegable si se desea
        productos_alerta = Producto.objects.filter(activo=True, stock__lte=F('punto_pedido'))[:5]
        
        return {
            'productos_criticos_count': productos_criticos_count,
            'productos_alerta': productos_alerta,
        }
    return {
        'productos_criticos_count': 0,
        'productos_alerta': [],
    }