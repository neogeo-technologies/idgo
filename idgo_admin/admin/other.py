from django.contrib import admin
from idgo_admin.models import Category
from idgo_admin.models import Financier
from idgo_admin.models import Jurisdiction
from idgo_admin.models import License
from idgo_admin.models import Task


class JurisdictionAdmin(admin.ModelAdmin):
    ordering = ("name", )
    search_fields = ('name', 'commune')


admin.site.register(Jurisdiction, JurisdictionAdmin)


class FinancierAdmin(admin.ModelAdmin):
    ordering = ("name", )
    search_fields = ('name', 'code')


admin.site.register(Financier, FinancierAdmin)


class LicensenAdmin(admin.ModelAdmin):
    ordering = ("title", )


admin.site.register(License, LicensenAdmin)


class CategoryAdmin(admin.ModelAdmin):
    model = Category
    readonly_fields = ('ckan_slug',)
    ordering = ('name',)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(CategoryAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


admin.site.register(Category, CategoryAdmin)


class TaskAdmin(admin.ModelAdmin):
    list_display = ('action', 'state', 'starting', 'end')
    ordering = ('starting', )
    readonly_fields = ('starting', )


admin.site.register(Task, TaskAdmin)
