from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def cop(valor):
    """Formatea un valor en pesos colombianos: 12500 -> $ 12.500"""
    try:
        valor = Decimal(valor)
    except Exception:
        return valor
    return '$ ' + f'{valor:,.0f}'.replace(',', '.')
