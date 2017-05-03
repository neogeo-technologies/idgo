from django.contrib import admin
from .models import Category, Commune, Territory, License, Projection, Resolution, AccessLevel, Resource, Dataset
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