from django.core.management.base import BaseCommand
from idgo_admin.ckan_module import CkanManagerHandler
from idgo_admin.models import Organisation


class Command(BaseCommand):

    help = "Supprimer les organisations CKAN qui n'ont aucun jeux de données."

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.ckan = CkanManagerHandler()

    def handle(self, *args, **options):
        for instance in Organisation.objects.all():
            organization = self.ckan.get_organization(
                str(instance.ckan_id), include_datasets=True)
            if not organization:
                continue
            if len(organization['packages']) > 0:
                continue
            self.ckan.purge_organization(str(instance.ckan_id))
