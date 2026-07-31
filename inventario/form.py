from django import forms
from .models import Producto


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = "__all__"
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "punto_pedido": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "unidad_medida": forms.TextInput(attrs={"class": "form-control"}),
            "precio_compra": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": 0,
            }),
            "precio_venta": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": 0,
            }),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "es_envase": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
