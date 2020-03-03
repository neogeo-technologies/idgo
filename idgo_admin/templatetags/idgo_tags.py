from django import template
from django.conf import settings

register = template.Library()

# settings value
@register.simple_tag
def settings_value(name, default_value=""):
    return getattr(settings, name, default_value)
