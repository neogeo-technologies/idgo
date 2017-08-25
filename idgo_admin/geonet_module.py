from django.conf import settings
from idgo_admin.utils import Singleton
from owslib.csw import CatalogueServiceWeb
from urllib.parse import urljoin


GEONET_URL = settings.GEONETWORK_URL
GEONET_USERNAME = settings.GEONETWORK_LOGIN
GEONET_PASSWORD = settings.GEONETWORK_PASSWORD
GEONET_TIMEOUT = 30


class GeonetUserHandler(metaclass=Singleton):

    def __init__(self):
        self.username = GEONET_USERNAME
        self.password = GEONET_PASSWORD
        self.remote = CatalogueServiceWeb(
            urljoin(GEONET_URL, 'srv/fre/csw-publication'),
            timeout=GEONET_TIMEOUT, lang='fr-FR',
            version='2.0.2', skip_caps=True,
            username=self.username, password=self.password)

    def _transaction(self, ttype, identifier, record):
        params = {
            'identifier': identifier,
            'record': record,
            'ttype': ttype,
            'typename': 'gmd:MD_Metadata'}
        return self.remote.transaction(**params)

    def get_record(self, id):
        res = self.remote.getrecordbyid(id=[id])
        if res and res.records:
            return res.records.get(id)

    def create_record(self, id, record):
        return self._transaction('insert', id, record)

    def update_record(self, id, record):
        return self._transaction('update', id, record)

GeonetUserHandler = GeonetUserHandler()
