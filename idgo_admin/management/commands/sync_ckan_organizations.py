from django.core.management.base import BaseCommand
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me

# from django.contrib.auth.models import User
# from idgo_admin.models import Dataset
# from idgo_admin.models import Organisation
from idgo_admin.models import Resource


class Command(BaseCommand):

    help = 'Synchroniser les organisations IDGO avec CKAN'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.ckan = ckan()
        self.ckan_me = ckan_me()

    def handle(self, *args, **options):
        # ckan_user = self.ckan_me(self.ckan.get_user(user.username)['apikey'])
        for res in Resource.objects.all():
            for org in res.organisations_allowed:
                print(org.ckan_slug)
