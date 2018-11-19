from django.contrib import admin
from django_admin_listfilter_dropdown.filters import DropdownFilter  #, RelatedDropdownFilter

from .models import Order
from .actions import download_csv

# def send_email(modeladmin, request, queryset):
#     queryset.update(status='p')
# send_email.short_description = "Mark selected stories as published"


class OrderAdmin(admin.ModelAdmin):

    date_hierarchy = 'date'

    list_display = ('date', 'applicant', 'email', 'organisation', 'terr', 'status')

    # ajout de l'email de l'utilisateur
    def email(self, obj):
        return obj.applicant.email
    email.short_description = 'E-mail'

    # ajout du nom du territoire de compétences
    def terr(self, obj):
        return obj.organisation.jurisdiction
    terr.short_description = 'Territoire de compétences'

    # action d'export en csv
    actions = [download_csv]
    download_csv.short_description = "Exporter en CSV"

    # list_filter = (('status', DropdownFilter),)  # erreur : Cannot resolve 
    # keyword 'organisation' into field. Choices are: accountactions, address, 
    # city, ckan_id, ckan_slug, dataset, description, email, geonet_id, id, 
    # is_active, is_crige_partner, jurisdiction, jurisdiction_id, 
    # liaisonscontributeurs, liaisonsreferents, license, license_id, logo, name, 
    # order, organisation_type, organisation_type_id, phone, postcode, profile,
    # profile_contributions, profile_referents, remoteckan, resource, website

# def send_email(modeladmin, request, queryset):
#     form = SendEmailForm(initial={'email': queryset})
#     return render(request, 'users/send_email.html', {'form': form})


admin.site.register(Order, OrderAdmin)
