from django.contrib.auth.models import User
from django.http import HttpResponse

from idgo_admin.models.mail import sender as mail_sender

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


def mail_list(modeladmin, request, queryset):
    mailList = []

    for obj in queryset:
        user = getattr(obj, 'applicant')
        email = User.objects.get(username=user).email
        mailList.append(email)
    return(mailList)


def mail_date_organisation(modeladmin, request, queryset, obj):

    user = getattr(obj, 'applicant')

    emailInfo = dict(
        email=User.objects.get(username=user).email,
        organisation=getattr(obj, 'organisation'),
        date=getattr(obj, 'date'))

    return emailInfo


def send_multiple_emails(modeladmin, request, queryset):
    mailList = mail_list(modeladmin, request, queryset)
    return webbrowser.open('mailto:?to={0}, &subject={1}'.format(','.join(mailList), 'Commande fichiers fonciers'))
    send_multiple_emails.short_description = "Envoyer un email"


def email_cadastre_wrong_files(modeladmin, request, queryset):

    for obj in queryset:

        emailInfo = mail_date_organisation(modeladmin, request, queryset, obj)

        return mail_sender(
                    'cadastre_wrong_file',
                    to=[emailInfo["email"]],
                    date=emailInfo["date"],
                    organisation=emailInfo["organisation"])


def email_cadastre_habilitation(modeladmin, request, queryset):

    for obj in queryset:

        emailInfo = mail_date_organisation(modeladmin, request, queryset, obj)

        return mail_sender(
                    'cadastre_no_habilitation',
                    to=[emailInfo["email"]],
                    date=emailInfo["date"],
                    organisation=emailInfo["organisation"]
                    )
