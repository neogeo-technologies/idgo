import csv
from django.http import HttpResponse
from io import StringIO


def download_csv(self, request, queryset):

    opts = self.model._meta

    f = StringIO()
    writer = csv.writer(f)
    field_names = [field.name for field in opts.fields]
    writer.writerow(field_names)

    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in field_names])

    f.seek(0)
    response = HttpResponse(f, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=stat-info.csv'
    return response
