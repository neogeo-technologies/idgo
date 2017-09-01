from django.core.management.base import BaseCommand
from idgo_admin.ckan_module import CkanManagerHandler
from idgo_admin.models import Category


class Command(BaseCommand):

    help = 'Synchroniser les catégories IDGO avec CKAN'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.ckan = CkanManagerHandler()

    def handle(self, *args, **options):
        for category in Category.objects.all():
            if self.ckan.is_group_exists(category.ckan_slug):
                self.stdout.write("'{0}' already exists".format(category.ckan_slug))
                continue
            self.ckan.add_group(category)
            self.stdout.write("'{0}' is created".format(category.ckan_slug))
