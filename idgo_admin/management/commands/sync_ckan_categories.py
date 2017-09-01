from django.core.management.base import BaseCommand
from idgo_admin.models import Category
from idgo_admin.ckan_module import CkanManagerHandler


class Command(BaseCommand):
    help = 'SYNCHRONISER LES CATEGORIES DJANGO ET LES GROUPES CKAN'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.ckan = CkanManagerHandler()

    def handle(self, *args, **options):

        for category in Category.objects.all():
            self.stdout.write(category.name)
            self.stdout.write('{} need to be added to CKAN?'.format(category.ckan_slug))
            if not self.ckan.is_group_exists(category.ckan_slug):
                self.stdout.write('No')
            else:
                self.stdout.write('Yes')
                self.ckan.add_group(category)
                if not self.ckan.is_group_exists(category.ckan_slug):
                    self.stdout.write('Error on add request', category.ckan_slug)
