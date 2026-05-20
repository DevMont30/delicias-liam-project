from django.urls import path
from .views import eliminar_carrito, home, agregar_carrito, ver_carrito, registro, finalizar_compra, mis_pedidos, generar_factura

urlpatterns = [
    path('', home, name='home'),
    path('agregar_carrito/<int:producto_id>/', agregar_carrito, name='agregar'),
    path('carrito/', ver_carrito, name='carrito'),
    path('registro/', registro, name='registro'),
    path('eliminar/<int:producto_id>/', eliminar_carrito, name='eliminar'),
    path('finalizar/', finalizar_compra, name='finalizar'),
    path('mis_pedidos/',mis_pedidos, name='mis_pedidos'),
    path('factura/<int:pedido_id>/',generar_factura, name='factura'),
]