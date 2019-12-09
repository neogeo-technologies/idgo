import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.models import Q
from django.utils.text import slugify

# TODO switcher sur modules idgo_admin.models
from sid.models import LiaisonsContributeurs
from sid.models import License
from sid.models import Organisation
from sid.models import OrganisationType
from sid.models import Profile
from sid.models import User
# from sid.exceptions import SidGenericError

logger = logging.getLogger('django')


PROFILE_SYNTAXE = {
    'AGENT_PROFILE': {
        'profile_element': 'agentProfile',
        'class_orga_type': 'ORGANISM',
        'orga_dept_element': 'organismDepartment',
        'orga_element': 'organism',
    },
    'EMPLOYEE_PROFILE': {
        'profile_element': 'employeeProfile',
        'class_orga_type': 'COMPANY',
        'orga_dept_element': 'companyDepartment',
        'orga_element': 'company',
    }
}


try:
    STOCK_DB = settings.DATABASES['sid_stock']['NAME']
except Exception:
    logger.exception('import_stock::SID STOCK_DB missing in settings')
    raise


class Command(BaseCommand):

    """
    il faudra qu’on intègre ces données dans une base temporaire
    de là on pourra faire une moulinette qui extrait les informations dont on a besoin dans un fichier
    on développe une fonction dans IDGO et Signalement pour initialiser la base des utilisateurs+organisation à partir de ce fichier
    ça te va ?
    fonction dans IDGO et Signalement -> un script plutôt ?
    faudrait peut-être demander confirmation à Seb et Guillaume que ça marcherait dans l’infra WL
    """

    organism_organisation_type, _ = OrganisationType.objects.get_or_create(
        code='organisme-public',
        defaults={'name': 'Organisme publique'}
    )
    company_organisation_type, _ = OrganisationType.objects.get_or_create(
        code='entreprise',
        defaults={'name': 'Entreprise'}
    )
    lic, _ = License.objects.get_or_create(
        slug='lov2',
        defaults={
            'url': 'https://www.etalab.gouv.fr/licence-ouverte-open-licence',
            'title': "Licence Ouverte Version 2.0",
        })

    def fetch_all(self, sql, db=STOCK_DB):

        with connections[db].cursor() as cursor:
            try:
                cursor.execute(sql)
                columns = [col[0] for col in cursor.description]
                io_data = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]
            except Exception:
                logger.exception("{} :: Error on SQL request: {} --".format(
                    db, sql))
                return None

        return io_data

    def save_logo(self, instance, logo_url):

        from django.core import files
        from urllib.request import urlopen
        try:
            logo = urlopen(logo_url)
            file_name = '{}_{}.{}'.format(
                instance.pk,
                instance.sid_id,
                {
                    'image/png': 'png', 'image/jpeg': 'jpg',
                    'image/tiff': 'tif', 'image/bmp': 'bmp',
                }.get(logo.headers.get('Content-Type', 'image/png'))
            )
            files.File(logo.fp)
            instance.logo.delete()
            instance.logo.save(file_name, files.File(logo.fp))
        except Exception:
            logger.exception('Logo url not available')

    def reformat_phone(self, in_phone):
        import re
        phone = ""
        if in_phone:
            try:
                m = re.search(r'(\w*)(\d{9})', in_phone.replace(' ', ''))
                phone = "0" + m.group(2)
            except Exception:
                pass
        return phone

    def create_organisation(self, data, class_type):

        if class_type == 'ORGANISM':
            organisation_type = self.organism_organisation_type
        else:
            organisation_type = self.company_organisation_type

        sid_id = data['id']
        structure_data = self.fetch_all("SELECT * FROM Structure where id='{}'".format(sid_id), STOCK_DB)
        legal_name = structure_data[0]['label']
        description = structure_data[0]['description']
        email = structure_data[0]['email']
        address = structure_data[0]['postalAddress']
        postcode = structure_data[0]['postalCode']
        city = structure_data[0]['city']
        website = structure_data[0]['website']
        phone = self.reformat_phone(structure_data[0]['phone'])

        logo_url = structure_data[0]['logoUrl']

        if Organisation.objects.filter(sid_id=sid_id).exists():
            logger.info("L'organisation sid_id: {} a déja été crée".format(sid_id))
            return None
        if Organisation.objects.filter(legal_name=legal_name).exists():
            logger.info("L'organisation legal_name: {} a déja été crée".format(legal_name))
            return None
        if Organisation.objects.filter(slug=slugify(legal_name)).exists():
            logger.info("L'organisation slug: {} a déja été crée".format(slugify(legal_name)))
            return None

        try:
            defaults = {
                'legal_name': legal_name,
                'description': description,
                'email': email,
                'address': address,
                'postcode': postcode,
                'city': city,
                'is_active': True,
                'sid_id': sid_id,
                'organisation_type': organisation_type,
                'website': website,
                'phone': phone,
                'license': self.lic,
                'geonet_id': None,
                'is_crige_partner': False,
                # 'jurisdiction': None  # Manquant
            }

            organisation = Organisation.objects.create(
                **defaults
            )
            # TODO url fermé aux non-authentifié
            # self.save_logo(organisation, logo_url)
        except Exception:
            logger.exception("Command::create_organisation")

        else:
            return organisation

    def create_profile(self, data, class_type):

        sid_id = data['id']

        if Profile.objects.filter(sid_id=sid_id).exists():
            logger.info("Le profile sid_id: {} a déja été crée".format(sid_id))
            return None
        if class_type == "EMPLOYEE":
            org_dept_id = data['companyDepartment_id']
            orga_dept = self.fetch_all("SELECT * FROM CompanyDepartment where id='{}';".format(org_dept_id))
            orga_sid_id = orga_dept[0]['company_id']

        elif class_type == "AGENT":
            org_dept_id = data['organismDepartment_id']
            orga_dept = self.fetch_all("SELECT * FROM OrganismDepartment where id='{}';".format(org_dept_id))
            orga_sid_id = orga_dept[0]['organism_id']

        structure_data = self.fetch_all("SELECT * FROM Structure where id='{}'".format(orga_sid_id), STOCK_DB)
        legal_name = structure_data[0]['label']

        try:
            orga_qs = Organisation.objects.filter(
                Q(sid_id=orga_sid_id) | Q(legal_name=legal_name)
            )
            orga = orga_qs.first() or None

            data_profile = self.fetch_all("SELECT * FROM Profile WHERE id='{}';".format(sid_id))
            if len(data_profile) == 0:
                logger.warning("Aucune instance Profile {} ne correspond en stock".format(sid_id))
                return None

            data_user = self.fetch_all("SELECT * FROM User WHERE id='{}';".format(data_profile[0]['user_id']))
            if len(data_user) == 0:
                logger.warning("Aucune instance User {} ne correspond en stock".format(data_profile[0]['user_id']))
                return None

            data_profil_role = self.fetch_all("SELECT * FROM Profile_Role WHERE profiles_id='{}';".format(sid_id))
            if len(data_profil_role) == 0:
                logger.warning("Aucune instance Profile_Role {} ne correspond en stock".format(sid_id))
                return None

            data_role = self.fetch_all("SELECT * FROM Role WHERE id='{}';".format(data_profil_role[0]['roles_id']))
            if len(data_role) == 0:
                logger.warning("Aucune instance Role {} ne correspond en stock".format(data_profil_role[0]['roles_id']))
                return None

            is_active = data_user[0]['enabled'] == b'\x01'

            if User.objects.filter(username=data_user[0]['username']).exists():
                logger.warning("L'User username: {} a déja été crée".format(data_user[0]['username']))
                return None

            user = User.objects.create(
                first_name=data_user[0]['firstname'],
                last_name=data_user[0]['lastname'],
                username=data_user[0]['username'],
                email=data_profile[0]['email'],

                is_superuser=data_role[0]['name'] == "administrateur",
                is_staff=data_role[0]['name'] == "administrateur",
                is_active=is_active,
            )

            profile = Profile.objects.create(
                sid_id=sid_id,
                user=user,
                organisation=orga,
                is_active=is_active,
                membership=orga is not None,
                # crige_membership,  # Manquant
                # is_admin,  # Manquant
                # sftp_password,  # Manquant
                # phone,  # Manquant
            )
            if orga:
                LiaisonsContributeurs.objects.create(
                    profile=profile,
                    organisation=orga
                )
        except Exception:
            logger.exception("Erreur à la création d'un utilisateur")
            logger.warning(data_user[0]['firstname'])
            logger.warning(data_user[0]['lastname'])
            logger.warning(data_profile[0]['email'])
            logger.warning(is_active)
        else:
            return profile

    def fetch_and_create(self, sql, class_type, DjangoModel):
        try:
            # On recupere les donnée du model sid central: AgentProfile / EmployeeProfile

            raw_data = self.fetch_all(sql, STOCK_DB)

            # logger.info('Model {}: import started, nb row: {}'.format(DjangoModel.__name__, len(raw_data)))
            if class_type in ['ORGANISM', 'COMPANY']:
                creator = self.create_organisation
            elif class_type in ['AGENT', 'EMPLOYEE']:
                creator = self.create_profile
            else:
                raise Exception("class_type undefined")
            for data in raw_data:
                creator(data, class_type)
        except Exception:
            logger.exception("L'import du model: {name} retourne l'erreur suivante".format(name=DjangoModel))
        else:
            if class_type == 'ORGANISM':
                count = DjangoModel.objects.filter(organisation_type__code='organisme-public').count()
            elif class_type == 'COMPANY':
                count = DjangoModel.objects.filter(organisation_type__code='entreprise').count()
            else:
                count = DjangoModel.objects.all().count()
            logger.info("Stock {} - Model {}: count():{} / rawdata:{} ".format(
                class_type, DjangoModel.__name__, count, len(raw_data))
            )

    def handle(self, *args, **options):
        # TODO doit-on vider avant chaque remplissage?
        User.objects.all().delete()
        Organisation.objects.all().delete()

        self.fetch_and_create(
            sql="""SELECT DISTINCT id FROM Organism;""",
            class_type='ORGANISM',
            DjangoModel=Organisation)

        self.fetch_and_create(
            sql="""SELECT DISTINCT id FROM Company;""",
            class_type='COMPANY',
            DjangoModel=Organisation)

        self.fetch_and_create(
            sql="""SELECT * FROM AgentProfile;""",
            class_type='AGENT',
            DjangoModel=Profile)

        self.fetch_and_create(
            sql="""SELECT * FROM EmployeeProfile;""",
            class_type='EMPLOYEE',
            DjangoModel=Profile)
