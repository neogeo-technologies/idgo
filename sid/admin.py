"""
POUR dev UNIQUEMENT
"""

from django.contrib import admin

from sid.models import Organisation
from sid.models import Profile

admin.site.register(Profile)
admin.site.register(Organisation)
