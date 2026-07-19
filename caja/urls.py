from django.urls import path
from . import views

app_name = 'caja'

urlpatterns = [
    path('', views.CierreCajaListView.as_view(), name='cierre_list'),
    path('<int:pk>/', views.CierreCajaDetailView.as_view(), name='cierre_detail'),
]