from django.conf import settings
from idgo_admin.utils import Singleton
from owslib.csw import CatalogueServiceWeb
from urllib.parse import urljoin
import requests


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

    def _get(self, url, params):
        r = requests.get(
            url, params=params, auth=(self.username, self.password))
        r.raise_for_status()
        return r

    def _q(self, identifier):
        r = self._get(urljoin(GEONET_URL, 'srv/fre/q'),
                      {'uuid': identifier, '_content_type': 'json'})
        metadata = r.json().get('metadata')
        if metadata \
                and len(metadata) == 1 \
                and metadata[0]['uuid'] == identifier:
            return metadata[0]['id']
        # Sinon error ?

    def _md_publish(self, identifier):
        return self._get(
            urljoin(GEONET_URL, 'srv/fre/md.publish'), {'ids': identifier})

    def _transaction(self, ttype, identifier, record):
        params = {
            'identifier': identifier,
            'record': record,
            'ttype': ttype,
            'typename': 'gmd:MD_Metadata'}
        return self.remote.transaction(**params)

    def get_record(self, id):
        self.remote.getrecordbyid(
            id=[id], outputschema='http://www.isotc211.org/2005/gmd')
        return self.remote.records.get(id)

    def create_record(self, id, record):
        return self._transaction('insert', id, record)

    def update_record(self, id, record):
        return self._transaction('update', id, record)

    def publish(self, id):
        return self._md_publish(self._q(id))


GeonetUserHandler = GeonetUserHandler()
