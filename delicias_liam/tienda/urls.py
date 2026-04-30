from django.urls import path
from .views import eliminar_carrito, home, agregar_carrito, ver_carrito, registro, finalizar_compra

urlpatterns = [
    path('', home, name='home'),
    path('agregar_carrito/<int:producto_id>/', agregar_carrito, name='agregar'),
    path('carrito/', ver_carrito, name='carrito'),
    path('registro/', registro, name='registro'),
    path('eliminar/<int:producto_id>/', eliminar_carrito, name='eliminar'),
    path('finalizar/', finalizar_compra, name='finalizar'),
]