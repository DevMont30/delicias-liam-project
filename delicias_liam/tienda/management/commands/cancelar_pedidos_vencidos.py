from django.core.management.base import BaseCommand

from tienda.services import cancelar_pedidos_vencidos


class Command(BaseCommand):
    help = 'Cancela los pedidos por transferencia sin comprobante después del tiempo límite y libera el stock.'

    def add_arguments(self, parser):
        parser.add_argument('--horas', type=int, default=None)

    def handle(self, *args, **options):
        n = cancelar_pedidos_vencidos(options['horas'])
        self.stdout.write(self.style.SUCCESS(f'Pedidos cancelados: {n}'))
