from django.core.management.base import BaseCommand
from idgo_admin.ckan_module import CkanManagerHandler
from idgo_admin.models import Category


class Command(BaseCommand):

    help = 'Synchroniser les catégories CKAN avec IDGO'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.ckan = CkanManagerHandler()

    def handle(self, *args, **options):
        for category in Category.objects.all():
            if self.ckan.is_group_exists(category.ckan_slug):
                category.ckan_id = self.ckan.get_group(category.ckan_slug)['id']
                category.save()
                self.stdout.write("'{0}' updated".format(category.ckan_slug))
