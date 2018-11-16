from django.contrib import admin
from .models import Order
from idgo_admin.models import Organisation # piste pour territoire de compétences


# def send_email(modeladmin, request, queryset):
#     queryset.update(status='p')
# send_email.short_description = "Mark selected stories as published"


class OrderAdmin(admin.ModelAdmin):

    list_display = ('date', 'applicant', 'organisation', 'status')


admin.site.register(Order, OrderAdmin)
