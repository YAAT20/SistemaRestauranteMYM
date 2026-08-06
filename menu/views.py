from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from .models import *
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.utils import timezone
from datetime import datetime, time, date
from decimal import Decimal, InvalidOperation
from django.views.generic import TemplateView
from .models import Receta
from inventario.models import Producto
from django.db.models import Count, Q

class ConfigurarPlatosDelDiaView(LoginRequiredMixin, View):
    template_name = 'menu/configurar_platos_del_dia.html'

    def get(self, request):
        fecha_str = request.GET.get('fecha')
        if fecha_str:
            try:
                fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                fecha_seleccionada = date.today()
        else:
            fecha_seleccionada = date.today()

        platos = Plato.objects.all().order_by('tipo', 'nombre')
        
        seleccionados = PlatoDelDia.objects.filter(fecha=fecha_seleccionada).values_list('plato_id', flat=True)
        
        return render(request, self.template_name, {
            'platos': platos,
            'seleccionados': list(seleccionados),
            'fecha_seleccionada': fecha_seleccionada.strftime('%Y-%m-%d'),
        })

    @transaction.atomic
    def post(self, request):
        # Captura directa y estricta priorizando GET (la URL)
        fecha_str = request.GET.get('fecha') or request.POST.get('fecha_configuracion')
        
        try:
            fecha_objetivo = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()
        except ValueError:
            fecha_objetivo = date.today()

        seleccionados = request.POST.getlist('platos')
        seleccionados_ids = [int(p_id) for p_id in seleccionados if p_id.isdigit()]

        # 1. Borramos únicamente los registros que ya NO están seleccionados para ESTA fecha objetivo
        PlatoDelDia.objects.filter(fecha=fecha_objetivo).exclude(plato_id__in=seleccionados_ids).delete()

        # 2. Iteramos y usamos update_or_create para garantizar que JAMÁS falle por clave duplicada
        for plato in Plato.objects.all():
            if plato.id in seleccionados_ids:
                stock_str = request.POST.get(f"stock_{plato.id}", "")
                stock = int(stock_str) if stock_str.isdigit() else plato.stock_diario

                precio_str = request.POST.get(f"precio_{plato.id}", "")
                if precio_str:
                    try:
                        precio = Decimal(precio_str.replace(",", "."))
                    except InvalidOperation:
                        precio = plato.precio
                else:
                    precio = plato.precio

                if fecha_objetivo == date.today():
                    plato.stock_diario = stock
                    plato.stock_actual = stock
                    plato.precio = precio
                    plato.disponible = True
                    plato.save()
                else:
                    plato.precio = precio
                    plato.save()

                # ESTA ES LA CLAVE: update_or_create actualiza si ya existe o lo crea si no existe
                PlatoDelDia.objects.update_or_create(
                    plato=plato,
                    fecha=fecha_objetivo,
                    defaults={}
                )
            else:
                if fecha_objetivo == date.today():
                    if plato.tipo in ['entrada', 'menu', 'carta', 'desayuno']:
                        plato.disponible = False
                        plato.save()

        messages.success(request, f'Platos configurados correctamente para la fecha: {fecha_objetivo}')
        return redirect(f"{reverse('menu:configurar_platos_del_dia')}?fecha={fecha_objetivo}")

class HistorialConfiguracionListView(LoginRequiredMixin, ListView):
    """Muestra una lista con todas las fechas que tienen platos programados"""
    model = PlatoDelDia
    template_name = 'menu/historial_configuracion_list.html'
    context_object_name = 'configuraciones_por_fecha'
    paginate_by = 10

    def get_queryset(self):
        # Agrupamos por fecha para mostrar cuántos platos tiene configurados cada día
        return (
            PlatoDelDia.objects.values('fecha')
            .annotate(
                total_platos=Count('id'),
                menus_count=Count('plato', filter=Q(plato__tipo='menu')),
                entradas_count=Count('plato', filter=Q(plato__tipo='entrada')),
                carta_count=Count('plato', filter=Q(plato__tipo='carta')),
                desayunos_count=Count('plato', filter=Q(plato__tipo='desayuno')),
            )
            .order_by('-fecha')
        )

class DetalleConfiguracionDiaView(LoginRequiredMixin, View):
    """Muestra el detalle completo de los platos configurados para una fecha específica"""
    template_name = 'menu/detalle_configuracion_dia.html'

    def get(self, request, fecha):
        platos_del_dia = PlatoDelDia.objects.filter(fecha=fecha).select_related('plato')
        
        contexto = {
            'fecha': fecha,
            'platos_del_dia': platos_del_dia,
        }
        return render(request, self.template_name, contexto)

class PlatoListView(LoginRequiredMixin, ListView):
    template_name = 'menu/plato_list.html'
    context_object_name = 'platos'

    def get_queryset(self):
        ahora = timezone.localtime().time()
        self.turno_tarde = (ahora >= time(15, 0) or ahora < time(8, 0))

        queryset = Plato.objects.filter(
            disponible=True,
            stock_actual__gt=0
        ).order_by("tipo", "nombre")

        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(nombre__icontains=q)
        ahora = timezone.localtime().time()
        self.turno_tarde = (ahora >= time(15, 0) or ahora < time(8, 0))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_platos'] = [
            {'tipo': 'desayuno', 'titulo': 'Desayunos', 'icono': 'fas fa-coffee', 'color': 'bg-warning-subtle'},
            {'tipo': 'entrada', 'titulo': 'Entradas del Día', 'icono': 'fas fa-leaf', 'color': 'bg-success-subtle'},
            {'tipo': 'menu',    'titulo': 'Platos del Menú',  'icono': 'fas fa-list', 'color': 'bg-info-subtle'},
            {'tipo': 'carta',   'titulo': 'Platos a la Carta','icono': 'fas fa-concierge-bell', 'color': 'bg-light'},
        ]
        context['turno_tarde'] = getattr(self, 'turno_tarde', False)
        return context

##Para que el cliente vea el menú del día
class CartaDelDiaView(TemplateView):
    template_name = "menu/carta_del_dia.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = timezone.localdate()

        platos_dia_qs = PlatoDelDia.objects.filter(fecha=hoy).select_related('plato')

        entradas = [pd.plato for pd in platos_dia_qs if pd.plato.tipo == 'entrada' and pd.plato.disponible]
        menus    = [pd.plato for pd in platos_dia_qs if pd.plato.tipo == 'menu' and pd.plato.disponible]
        desayunos = [pd.plato for pd in platos_dia_qs if pd.plato.tipo == 'desayuno' and pd.plato.disponible]
        carta    = [pd.plato for pd in platos_dia_qs if pd.plato.tipo == 'carta' and pd.plato.disponible]

        context.update({
            "fecha": hoy,
            "entradas": entradas,
            "menus": menus,
            "desayunos": desayunos,
            "carta": carta,
        })
        return context

class PlatoCreateView(CreateView):
    model = Plato
    template_name = 'menu/plato_form.html'
    fields = ['nombre', 'precio', 'tipo', 'disponible', 'stock_diario']
    success_url = reverse_lazy('menu:plato_list')
    
    def form_valid(self, form):
        # Cuando se crea, inicializamos stock_actual igual que stock_diario
        form.instance.stock_actual = form.instance.stock_diario
        messages.success(self.request, 'Plato creado exitosamente con stock inicial')
        return super().form_valid(form)

class PlatoUpdateView(UpdateView):
    model = Plato
    template_name = 'menu/plato_form.html'
    fields = ['nombre', 'precio', 'tipo', 'disponible', 'stock_diario']
    success_url = reverse_lazy('menu:plato_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Plato actualizado exitosamente')
        return super().form_valid(form)

class PlatoDeleteView(DeleteView):
    model = Plato
    template_name = 'menu/plato_confirm_delete.html'
    success_url = reverse_lazy('menu:plato_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Plato eliminado exitosamente')
        return super().delete(request, *args, **kwargs)

def toggle_disponibilidad(request, pk):
    plato = get_object_or_404(Plato, pk=pk)
    plato.disponible = not plato.disponible
    plato.save()
    
    action = "disponible" if plato.disponible else "no disponible"
    messages.success(request, f'Plato marcado como {action}')
    
    return redirect('menu:plato_list')

class ReponerStockView(LoginRequiredMixin, View):
    template_name = 'menu/reponer_stock.html'
    
    def get(self, request):
        platos = Plato.objects.all()
        return render(request, self.template_name, {'platos': platos})
    
    def post(self, request):
        for plato in Plato.objects.all():
            cantidad = request.POST.get(f'plato_{plato.id}', 0)
            if cantidad:
                plato.reponer_stock(int(cantidad))
        
        messages.success(request, 'Stock diario actualizado correctamente')
        return redirect('menu:plato_list')
    
def asignar_ingrediente(request, plato_id):
    plato = get_object_or_404(Plato, id=plato_id)
    productos = Producto.objects.all()  # todos los insumos del inventario

    if request.method == "POST":
        producto_id = request.POST.get("producto")
        cantidad = request.POST.get("cantidad")
        unidad = request.POST.get("unidad")

        if producto_id and cantidad:
            producto = get_object_or_404(Producto, id=producto_id)

            # Si ya existe el producto en la receta → actualizar
            receta, creada = Receta.objects.get_or_create(
                plato=plato,
                producto=producto,
                defaults={"cantidad": cantidad, "unidad": unidad or "unidad"}
            )
            if not creada:
                receta.cantidad = cantidad
                receta.unidad = unidad or receta.unidad
                receta.save()

        return redirect("menu:plato_list")

    return render(request, "menu/asignar_ingrediente.html", {
        "plato": plato,
        "productos": productos
    })