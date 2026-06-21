from django import template

register = template.Library()


@register.filter
def split(value, arg):
    """Split a string by a delimiter. Usage: {{ value|split:"," }}"""
    return value.split(arg)
