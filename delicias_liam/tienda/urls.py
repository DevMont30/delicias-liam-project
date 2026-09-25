from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('producto/<int:producto_id>/', views.detalle_producto, name='producto'),
    path('carrito/', views.ver_carrito, name='carrito'),
    path('carrito/agregar/<int:producto_id>/', views.agregar_carrito, name='agregar'),
    path('carrito/actualizar/', views.actualizar_carrito, name='actualizar'),
    path('carrito/eliminar/', views.eliminar_carrito, name='eliminar'),
    path('registro/', views.registro, name='registro'),
    path('finalizar/', views.checkout, name='finalizar'),
    path('mis_pedidos/', views.mis_pedidos, name='mis_pedidos'),
    path('pedido/<int:pedido_id>/', views.detalle_pedido, name='pedido'),
    path('pedido/<int:pedido_id>/cancelar/', views.cancelar_pedido, name='cancelar_pedido'),
    path('factura/<int:pedido_id>/', views.factura, name='factura'),
    path('politica-de-datos/', views.politica_datos, name='politica_datos'),
    path('terminos-y-condiciones/', views.terminos, name='terminos'),
    path('panel/', views.panel, name='panel'),
    path('panel/reportes/', views.reportes, name='reportes'),
]
