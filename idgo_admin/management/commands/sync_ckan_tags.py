from django.core.management.base import BaseCommand
from idgo_admin.ckan_module import CkanManagerHandler
from idgo_admin.models import DataType
from idgo_admin.models import Support


class Command(BaseCommand):

    help = 'Synchroniser les tags IDGO avec CKAN'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.ckan = CkanManagerHandler()

    def sync_tags(self, data, vocabulary_name):
        vocabulary = self.ckan.get_vocabulary(vocabulary_name)
        if not vocabulary:
            self.ckan.create_vocabulary(vocabulary, [entry.ckan_slug for entry in data])
            self.stdout.write("New vocabulary '{0}' created".format(entry.ckan_slug))
        else:
            for entry in data:
                if self.ckan.is_tag_exists(
                        entry.ckan_slug, vocabulary_id=vocabulary['id']):
                    self.stdout.write("'{0}' already sync".format(entry.ckan_slug))
                    continue
                self.ckan.create_tag(
                    entry.ckan_slug, vocabulary_id=vocabulary['id'])
                self.stdout.write("'{0}' added".format(entry.ckan_slug))

    def handle(self, *args, **options):
        self.sync_tags(DataType.objects.all(), 'data_type')
        self.sync_tags(Support.objects.all(), 'support')
        self.stdout.write('Done!')
