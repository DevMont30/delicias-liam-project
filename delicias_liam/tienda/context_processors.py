from django.conf import settings

from .carrito import Carrito
from .models import Categoria


def tienda(request):
    datos = settings.DELICIAS_LIAM
    return {
        'carrito_cantidad': len(Carrito(request)),
        'categorias_menu': Categoria.objects.filter(activa=True),
        'whatsapp': datos['WHATSAPP'],
        'instagram': datos['INSTAGRAM'],
    }
