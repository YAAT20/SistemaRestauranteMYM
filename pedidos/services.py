from django.utils import timezone
from django.db import transaction

def imprimir_pedido_cocina(pedido):

    detalles_nuevos = pedido.detalles.filter(preparado=False)

    if not detalles_nuevos.exists():
        return False, "No hay ítems nuevos para enviar a cocina.", None

    ya_enviado = pedido.detalles.filter(preparado=True).exists()
    
    lineas_ticket = []
    lineas_ticket.append("***** AGREGADO AL PEDIDO *****" if ya_enviado else "***** PEDIDO NUEVO *****")
    lineas_ticket.append(f"Mesa: {pedido.mesa.numero}")
    lineas_ticket.append(f"Pedido #{pedido.numero_diario}")
    lineas_ticket.append(f"Hora: {timezone.localtime().strftime('%H:%M:%S')}")
    lineas_ticket.append("------------------------------")

    for det in detalles_nuevos:
        nombre = det.plato.nombre if det.plato else det.producto.nombre
        lineas_ticket.append(f"{det.cantidad}x {nombre}")
        if det.observaciones:
            lineas_ticket.append(f"   (Obs: {det.observaciones})")

    lineas_ticket.append("------------------------------")
    lineas_ticket.append("\n\n\n")

    texto_final = "\n".join(lineas_ticket)

    try:
        with transaction.atomic():
            detalles_nuevos.update(
                preparado=True,
                hora_impresion=timezone.localtime()
            )
        return True, None, texto_final
    except Exception as e:
        return False, f"Error de BD: {str(e)}", None
    
def reimprimir_pedido_completo(pedido):

    todos_los_detalles = pedido.detalles.all()

    if not todos_los_detalles.exists():
        return False, "El pedido no tiene ítems para imprimir.", None

    lineas_ticket = []
    lineas_ticket.append("***** REIMPRESIÓN (COPIA) *****")
    lineas_ticket.append(f"Mesa: {pedido.mesa.numero}")
    lineas_ticket.append(f"Pedido #{pedido.numero_diario}")
    lineas_ticket.append(f"Hora ref: {timezone.localtime().strftime('%H:%M:%S')}")
    lineas_ticket.append("------------------------------")

    for det in todos_los_detalles:
        # Aseguramos de obtener el nombre ya sea un plato o un producto directo
        nombre = det.plato.nombre if det.plato else det.producto.nombre
        lineas_ticket.append(f"{det.cantidad}x {nombre}")
        
        if det.observaciones:
            lineas_ticket.append(f"   (Obs: {det.observaciones})")

    lineas_ticket.append("------------------------------")
    lineas_ticket.append("\n\n\n")

    texto_final = "\n".join(lineas_ticket)

    return True, None, texto_final