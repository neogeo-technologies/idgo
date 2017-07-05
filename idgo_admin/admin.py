from .models import AccessLevel
from .models import Category
from .models import Commune
from .models import Dataset
from .models import License
from .models import Projection
from .models import Resolution
from .models import Resource
from .models import Territory
from django.contrib import admin


# Register your models here.
admin.site.register(Category)
admin.site.register(License)
admin.site.register(Commune)
admin.site.register(Territory)
admin.site.register(Projection)
admin.site.register(Resolution)
admin.site.register(AccessLevel)


class ResourceInline(admin.StackedInline):
    model = Resource
    max_num = 5
    can_delete = True
    readonly_fields = ('bbox',)


class DatasetAdmin(admin.ModelAdmin):
    inlines = [ResourceInline]


admin.site.register(Dataset, DatasetAdmin)
