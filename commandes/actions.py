from django.contrib.auth.models import User
from django.http import HttpResponse
from django.utils.html import format_html

import unicodecsv
import webbrowser


def export_as_csv_action(description="Export selected objects as CSV file",
                         fields=None, exclude=None, header=True):
    """
    This function returns an export csv action
    'fields' and 'exclude' work like in django ModelForm
    'header' is whether or not to output the column names as the first row
    """
    def export_as_csv_cadastre(modeladmin, request, queryset):
        opts = modeladmin.model._meta

        if not fields:
            field_names = [field.name for field in opts.fields]
        else:
            field_names = fields
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=%s.csv' % str(opts).replace('.', '_')

        writer = unicodecsv.writer(response, encoding='utf-8')
        if header:
            custom_fild_names = field_names.copy()
            custom_fild_names.append('email')
            writer.writerow(custom_fild_names)
        for obj in queryset:
            row = [getattr(obj, field)() if callable(getattr(obj, field)) else getattr(obj, field) for field in field_names]
            email = User.objects.get(username=row[3]).email
            row.append(email)
            writer.writerow(row)
        return response
    export_as_csv_cadastre.short_description = description
    return export_as_csv_cadastre


def send_multiple_emails(modeladmin, request, queryset):
    mailList = []
    for obj in queryset:
        user = getattr(obj, 'applicant')
        email = User.objects.get(username=user).email
        mailList.append(email)
    return webbrowser.open('mailto:?to={0}, &subject={1}'.format(','.join(mailList), 'Commande fichiers fonciers'))
    send_multiple_emails.short_description = "Envoyer un email"
