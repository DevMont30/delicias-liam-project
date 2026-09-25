from django.core.management.base import BaseCommand

from tienda.models import Categoria, Producto

# Categorías sugeridas y palabras clave para asignar los productos existentes.
# Ajústelas a la oferta real de Delicias Liam.
CATEGORIAS = [
    ('Postres fríos', ['tres leches', 'cheesecake', 'tarta de queso']),
    ('Tortas', ['torta', 'brazo de reina']),
    ('Galletas y brownies', ['galleta', 'brownie']),
    ('Hojaldres y pasteles', ['milhoja', 'pastel', 'hojaldre']),
    ('Panadería', ['almojábana', 'almojabana', 'pan ']),
    ('Detalles y obsequios', ['ancheta', 'caja sorpresa', 'peluche', 'rosa']),
]


class Command(BaseCommand):
    help = 'Crea las categorías sugeridas y asigna los productos que aún no tienen categoría.'

    def handle(self, *args, **options):
        for orden, (nombre, claves) in enumerate(CATEGORIAS):
            cat, creada = Categoria.objects.get_or_create(nombre=nombre, defaults={'orden': orden})
            if creada:
                self.stdout.write(f'Categoría creada: {nombre}')
            for p in Producto.objects.filter(categoria__isnull=True):
                if any(c in p.nombre.lower() for c in claves):
                    p.categoria = cat
                    p.save(update_fields=['categoria'])
                    self.stdout.write(f'  {p.nombre} -> {nombre}')
        pendientes = Producto.objects.filter(categoria__isnull=True).count()
        self.stdout.write(self.style.SUCCESS(f'Listo. Productos sin categoría: {pendientes}'))
