from django.apps import AppConfig
from django.db.models.signals import post_migrate


ROLES = {
    'Administrador': {
        'tienda': ['categoria', 'producto', 'movimientoinventario', 'pedido', 'detallepedido', 'pago',
                   'historialestado', 'direccion', 'perfilcliente'],
        'auth': ['user'],
        'extras': ['tienda.ver_reportes'],
    },
    'Inventario': {
        'tienda': ['categoria', 'producto', 'movimientoinventario'],
        'solo_ver': ['pedido', 'detallepedido'],
    },
    'Ventas': {
        'tienda': ['pedido', 'pago', 'historialestado'],
        'solo_ver': ['producto', 'detallepedido', 'direccion', 'perfilcliente'],
    },
}


def crear_roles(sender, **kwargs):
    """Crea (o actualiza) los grupos de usuarios con sus permisos."""
    from django.apps import apps
    from django.contrib.auth.management import create_permissions
    from django.contrib.auth.models import Group, Permission

    # Asegura que existan los permisos de todos los modelos antes de asignarlos
    for app_config in apps.get_app_configs():
        create_permissions(app_config, verbosity=0, using=kwargs.get('using', 'default'))

    for nombre, conf in ROLES.items():
        grupo, _ = Group.objects.get_or_create(name=nombre)
        perms = []
        for app in ('tienda', 'auth'):
            for modelo in conf.get(app, []):
                perms += list(Permission.objects.filter(content_type__app_label=app, content_type__model=modelo)
                              .exclude(codename='ver_reportes'))
        for modelo in conf.get('solo_ver', []):
            perms += list(Permission.objects.filter(content_type__app_label='tienda',
                                                    codename=f'view_{modelo}'))
        for extra in conf.get('extras', []):
            app, codename = extra.split('.')
            perms += list(Permission.objects.filter(content_type__app_label=app, codename=codename))
        grupo.permissions.set(perms)


class TiendaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tienda'
    verbose_name = 'Tienda Delicias Liam'

    def ready(self):
        post_migrate.connect(crear_roles, sender=self)
