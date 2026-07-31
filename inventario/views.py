# inventario/views.py

from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
)

from usuarios.mixins import AdminRequiredMixin
from .models import Producto, MovimientoInventario
from .form import ProductoForm


class ProductoListView(LoginRequiredMixin, ListView):
    model = Producto
    template_name = "inventario/producto_list.html"
    context_object_name = "productos"
    ordering = ["nombre"]


class ProductoCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Producto
    form_class = ProductoForm
    template_name = "inventario/producto_form.html"
    success_url = reverse_lazy("inventario:producto_list")


class ProductoUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Producto
    form_class = ProductoForm
    template_name = "inventario/producto_form.html"
    success_url = reverse_lazy("inventario:producto_list")


class ProductoDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Producto
    template_name = "inventario/producto_confirm_delete.html"
    success_url = reverse_lazy("inventario:producto_list")


class MovimientoInventarioListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = MovimientoInventario
    template_name = "inventario/movimiento_list.html"
    context_object_name = "movimientos"
    paginate_by = 20

    def get_queryset(self):
        return (
            MovimientoInventario.objects
            .select_related("producto", "plato", "usuario", "pedido")
            .order_by("-fecha")
        )
