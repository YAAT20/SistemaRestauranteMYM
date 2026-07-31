from django.db import models
from django.core.exceptions import ValidationError
from menu.models import Plato
from usuarios.models import Usuario
from django.utils import timezone
from inventario.models import Producto, MovimientoInventario
from django.db import transaction
from datetime import time
from urllib.parse import quote
from datetime import datetime, time
from decimal import Decimal

class Mesa(models.Model):
    ESTADOS = (
        ('LIBRE', 'Libre'),
        ('OCUPADA', 'Ocupada'),
    )
    
    numero = models.PositiveIntegerField(unique=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='LIBRE')
    capacidad = models.PositiveIntegerField(default=4)  # Adicionado

    def __str__(self):
        return f"Mesa {self.numero}"

class Cliente(models.Model):
    nombre = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=15, unique=True)

    def __str__(self):
        return f"{self.nombre} ({self.telefono})" if self.nombre else self.telefono

    def link_whatsapp_carta(self):
        enlace = "http://tuservidor.com/menu/carta/"  # 👈 aquí pon tu dominio real
        mensaje = f"Hola {self.nombre}, aquí tienes la carta del día: {enlace}"
        return f"https://api.whatsapp.com/send?phone={self.telefono}&text={quote(mensaje)}"

class Pedido(models.Model):
    ESTADOS_PEDIDO = (
        ('PENDIENTE', 'Pendiente'),
        ('EN_COCINA', 'En cocina'),
        ('EN_PREPARACION', 'En preparación'),
        ('COMPLETO', 'Completo - Espera de pago'),
        ('PAGADO', 'Pagado'),
        ('CANCELADO', 'Cancelado'),
    )
    TURNOS = (
        ('MAÑANA', 'Mañana (8am-3pm)'),
        ('TARDE', 'Tarde (3pm-12am)')
    )
    # 🆕 Tipos de pedido (Local o Para Llevar)
    TIPOS_PEDIDO = (
        ('LOCAL', 'Consumo en Local'),
        ('LLEVAR', 'Para Llevar'),
    )
    tipo = models.CharField(max_length=10, choices=TIPOS_PEDIDO, default='LOCAL')
    
    turno = models.CharField(max_length=10, choices=TURNOS, blank=True)
    
    # ⚠️ Mesa opcional (null=True, blank=True) para pedidos Para Llevar
    mesa = models.ForeignKey(Mesa, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos")
    
    mozo = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='pedidos')
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos')
    fecha_hora = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=15, choices=ESTADOS_PEDIDO, default='PENDIENTE')
    observaciones = models.TextField(blank=True)
    enviado_cocina = models.BooleanField(default=False)
    fecha_pago = models.DateTimeField(null=True, blank=True)
    es_cortesia = models.BooleanField(default=False, help_text="Si es True, no suma en ventas ni caja")
    numero_diario = models.PositiveIntegerField(editable=False, null=True, blank=True, default=None)

    def clean(self):
        super().clean()
        if self.tipo == 'LOCAL' and not self.mesa:
            raise ValidationError("Los pedidos de consumo en local deben tener una mesa asignada.")

    def save(self, *args, **kwargs):
        self.full_clean()
        ahora_local = timezone.localtime(timezone.now())
        
        if not self.turno:
            self.turno = 'MAÑANA' if time(8, 0) <= ahora_local.time() < time(15, 0) else 'TARDE'
        
        if self.pk is None and self.numero_diario is None:
            fecha_local = ahora_local.date()
            inicio_dia = timezone.make_aware(datetime.combine(fecha_local, time.min))
            fin_dia = timezone.make_aware(datetime.combine(fecha_local, time.max))
            
            with transaction.atomic():
                ultimo = Pedido.objects.select_for_update().filter(
                    fecha_hora__gte=inicio_dia,
                    fecha_hora__lte=fin_dia
                ).aggregate(
                    max_num=models.Max("numero_diario")
                )["max_num"] or 0
                
                self.numero_diario = ultimo + 1
        
        super().save(*args, **kwargs)

    @transaction.atomic
    def agregar_plato(self, plato, cantidad, usuario, observaciones=""):
        plato = Plato.objects.select_for_update().get(pk=plato.pk)
        plato.descontar_stock(cantidad=cantidad, usuario=usuario, pedido=self)
        precio = plato.precio or 0

        DetallePedido.objects.create(
            pedido=self, plato=plato, cantidad=cantidad, precio_unitario=precio, observaciones=observaciones
        )

    @transaction.atomic
    def agregar_producto(self, producto, cantidad, usuario, descripcion=None):
        producto = Producto.objects.select_for_update().get(pk=producto.pk)
        if producto.stock < cantidad:
            raise ValueError(f"No hay suficiente stock para {producto.nombre}")

        producto.ajustar_stock(
            cantidad=cantidad, tipo=MovimientoInventario.TIPO_SALIDA, usuario=usuario, pedido=self, descripcion=descripcion or f"Pedido #{self.id}"
        )

        DetallePedido.objects.create(
            pedido=self, producto=producto, cantidad=cantidad, precio_unitario=producto.precio_venta
        )

    @transaction.atomic
    def reponer_detalle(self, detalle, usuario):
        if detalle.plato:
            detalle.plato.reponer_stock(cantidad=detalle.cantidad, usuario=usuario, descripcion=f"Reversión edición pedido #{self.id}")
        elif detalle.producto:
            detalle.producto.ajustar_stock(cantidad=detalle.cantidad, tipo=MovimientoInventario.TIPO_ENTRADA, usuario=usuario, pedido=self, descripcion=f"Reversión edición pedido #{self.id}")
            
    @transaction.atomic
    def cambiar_estado(self, nuevo_estado, usuario=None):
        estados_validos = [e[0] for e in self.ESTADOS_PEDIDO]
        if nuevo_estado not in estados_validos:
            raise ValueError(f"Estado inválido: {nuevo_estado}")

        if nuevo_estado == 'CANCELADO' and self.estado != 'CANCELADO':
            for detalle in self.detalles.all():
                if detalle.plato:
                    detalle.plato.reponer_stock(cantidad=detalle.cantidad, usuario=usuario, descripcion=f"Reversión por cancelación pedido #{self.numero_diario}")
                elif detalle.producto:
                    detalle.producto.ajustar_stock(cantidad=detalle.cantidad, tipo=MovimientoInventario.TIPO_ENTRADA, usuario=usuario, pedido=self, descripcion=f"Reversión por cancelación pedido #{self.numero_diario}")

        self.estado = nuevo_estado
        if nuevo_estado == 'EN_COCINA':
            self.enviado_cocina = True
        self.save()

        return f"Pedido #{self.numero_diario} actualizado a {self.get_estado_display()}"

    @property
    def total(self):
        if self.es_cortesia:
            return 0
        return sum(detalle.subtotal for detalle in self.detalles.all())

    @property
    def total_pagado(self):
        return sum(pago.monto for pago in self.pagos.all())

    @property
    def saldo_pendiente(self):
        if self.es_cortesia:
            return 0
        return max(Decimal('0.00'), self.total - self.total_pagado)

    def registrar_pago(self, metodo, monto, usuario, referencia=None):
        if self.es_cortesia:
            raise ValidationError("Este pedido es de cortesía, no se puede registrar pagos.")
        
        monto = Decimal(str(monto))
        if monto <= 0:
            raise ValidationError("El monto a pagar debe ser mayor a 0.")

        if monto > self.saldo_pendiente:
            raise ValidationError(f"El monto (S/ {monto}) excede el saldo pendiente (S/ {self.saldo_pendiente}).")

        pago = Pago.objects.create(
            pedido=self, metodo=metodo, monto=monto, referencia=referencia, usuario=usuario
        )

        if self.saldo_pendiente == 0:
            self.estado = 'PAGADO'
            self.fecha_pago = timezone.now()
            self.save()

        return pago


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    plato = models.ForeignKey(Plato, on_delete=models.PROTECT, null=True, blank=True)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, null=True, blank=True)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    observaciones = models.TextField(blank=True)
    preparado = models.BooleanField(default=False)
    hora_impresion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        if self.plato:
            return f"{self.cantidad}x {self.plato.nombre} (Pedido {self.pedido.id})"
        elif self.producto:
            return f"{self.cantidad}x {self.producto.nombre} (Pedido {self.pedido.id})"
        return f"{self.cantidad}x Sin nombre (Pedido {self.pedido.id})"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def save(self, *args, **kwargs):
        if not self.pk and not self.precio_unitario:
            if self.plato:
                self.precio_unitario = self.plato.precio
            elif self.producto:
                self.precio_unitario = self.producto.precio_venta
        super().save(*args, **kwargs)


class Boleta(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE)
    numero = models.CharField(max_length=20, unique=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    enviada_whatsapp = models.BooleanField(default=False)
    fecha_envio_whatsapp = models.DateTimeField(null=True, blank=True)
    archivo_pdf = models.FileField(upload_to='boletas/', blank=True, null=True) #boleta en pdf
    respuesta_api = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Boleta {self.numero}"

class Pago(models.Model):
    METODOS_PAGO = (
        ('EFECTIVO', 'Efectivo'),
        ('YAPE', 'Yape'),
        ('PLIN', 'Plin'),
        ('TARJETA_DEBITO', 'Tarjeta de Débito'),
        ('TARJETA_CREDITO', 'Tarjeta de Crédito'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('OTRO', 'Otro'),
    )

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='pagos')
    metodo = models.CharField(max_length=20, choices=METODOS_PAGO)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    referencia = models.CharField(max_length=100, blank=True, null=True, help_text="Número de operación, voucher o Yape")
    fecha_hora = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, help_text="Cajero o mozo que registró el pago")

    def __str__(self):
        return f"Pago #{self.id} - {self.get_metodo_display()} S/ {self.monto} (Pedido #{self.pedido.numero_diario or self.pedido.id})"