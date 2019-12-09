import logging

from django.conf import settings
from django.core.management.base import BaseCommand

# TODO switcher sur modules idgo_admin.models
from sid.models import Profile
from sid.models import User


logger = logging.getLogger('django')


class Command(BaseCommand):

    def add_arguments(self, parser):

        parser.add_argument(
            '--password',
            required=False,
            dest='pwd',
            help="ce mot de passe sera utiliser à la place de celui defini dans les settings"
        )

    def handle(self, *args, **options):
        pwd = options['pwd']
        if not pwd:
            password = getattr(settings, "SUPER_PASSWORD", "passpass")

        username = getattr(settings, "SUPER_USERNAME", "admin")
        email = getattr(settings, "SUPER_EMAIL", "admin@notdefined.no")
        sid_id = getattr(settings, "SUPER_UID", "UIDMISSING")

        user = User.objects.create_superuser(
            username=username, email=email, password=password)

        profile = Profile.objects.create(user=user, sid_id=sid_id)
        logger.info("Profile created OK: {}".format(profile.user.username))
