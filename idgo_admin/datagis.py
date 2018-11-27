# Copyright (c) 2017-2018 Datasud.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import datetime
from django.apps import apps
from django.conf import settings
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.gdal.error import SRSException
from django.contrib.gis.gdal import GDALRaster
from django.db import connections
from django.utils.encoding import DjangoUnicodeDecodeError
from idgo_admin.exceptions import DatagisBaseError
from idgo_admin.exceptions import ExceedsMaximumLayerNumberFixedError
from idgo_admin.utils import slugify
from pathlib import Path
import re
from uuid import uuid4


DATABASE = settings.DATAGIS_DB
OWNER = settings.DATABASES[DATABASE]['USER']
MRA_DATAGIS_USER = settings.MRA['DATAGIS_DB_USER']


SCHEMA = 'public'
THE_GEOM = 'the_geom'
TO_EPSG = 4171


class NotDataGISError(DatagisBaseError):
    message = "Le fichier reçu n'est pas reconnu comme étant un jeu de données SIG."


class NotFoundSrsError(DatagisBaseError):
    message = "Le système de coordonnées n'est pas reconnu."


class NotGDALError(DatagisBaseError):
    message = "Le fichier reçu n'est pas reconnu comme étant un jeu de données matriciel."


class NotOGRError(DatagisBaseError):
    message = "Le fichier reçu n'est pas reconnu comme étant un jeu de données vectoriel."


class NotSupportedSrsError(DatagisBaseError):
    message = "Le système de coordonnées n'est pas supporté par l'application."


class DataDecodingError(DatagisBaseError):
    message = "Impossible de décoder les données correctement."


class SQLError(DatagisBaseError):
    message = "Le fichier reçu n'est pas reconnu comme étant un jeu de données SIG."


def is_valid_epsg(code):
    sql = '''SELECT * FROM public.spatial_ref_sys WHERE auth_srid = '{}';'''.format(code)
    with connections[DATABASE].cursor() as cursor:
        try:
            cursor.execute(sql)
        except Exception as e:
            if e.__class__.__qualname__ != 'ProgrammingError':
                raise e
        records = cursor.fetchall()
        cursor.close()
    return len(records) == 1


def get_proj4s():
    sql = '''SELECT auth_srid, proj4text FROM public.spatial_ref_sys;'''
    with connections[DATABASE].cursor() as cursor:
        try:
            cursor.execute(sql)
        except Exception as e:
            if e.__class__.__qualname__ != 'ProgrammingError':
                raise e
        records = cursor.fetchall()
        cursor.close()
    return records


def retreive_epsg_through_proj4(proj4):

    def parse(line):
        matches = re.finditer('\+(\w+)(=([a-zA-Z0-9\.\,]+))?', line)
        return set(match.group(0) for match in matches)

    parsed_proj4 = parse(proj4)
    candidate = []
    for row in get_proj4s():
        tested = parse(row[1])
        if not len(parsed_proj4 - tested) and len(tested - parsed_proj4) < 2:
            candidate.append(row[0])
    if len(candidate) == 1:
        return candidate[0]


def retreive_epsg_through_regex(text):

    SupportedCrs = apps.get_model(
        app_label='idgo_admin', model_name='SupportedCrs')

    for supported_crs in SupportedCrs.objects.all():
        if not supported_crs.regex:
            continue
        if re.match(supported_crs.regex, text, flags=re.IGNORECASE):
            return supported_crs.auth_code


class GdalOpener(object):

    _raster = None

    def __init__(self, filename, extension=None):

        if extension == 'zip':
            filename = '/vsizip/{}'.format(filename)

        try:
            self._raster = GDALRaster(filename)
        except GDALException as e:
            raise NotGDALError(
                'The file received is not recognized as being a GIS raster data. {}'.format(e.__str__()))

    def get_raster(self):
        return self._raster


class OgrOpener(object):

    _datastore = None

    def __init__(self, filename, extension=None):

        if extension == 'zip':
            filename = '/vsizip/{}'.format(filename)

        try:
            self._datastore = DataSource(filename)
        except GDALException as e:
            raise NotOGRError(
                'The file received is not recognized as being a GIS vector data. {}'.format(e.__str__()))

    def get_layers(self):
        return self._datastore


def get_gdalogr_object(filename, extension):
    try:
        return GdalOpener(filename, extension=extension)
    except NotGDALError:
        try:
            return OgrOpener(filename, extension=extension)
        except NotOGRError:
            raise NotDataGISError()


CREATE_TABLE = '''
CREATE TABLE {schema}."{table}" (
  fid serial NOT NULL,
  {attrs},
  {the_geom} geometry({geometry}, {to_epsg}),
  CONSTRAINT "{table}_pkey" PRIMARY KEY (fid)) WITH (OIDS=FALSE);
ALTER TABLE {schema}."{table}" OWNER TO {owner};
COMMENT ON TABLE {schema}."{table}" IS '{description}';
CREATE UNIQUE INDEX "{table}_fid" ON {schema}."{table}" USING btree (fid);
CREATE INDEX "{table}_gix" ON {schema}."{table}" USING GIST ({the_geom});
GRANT SELECT ON TABLE  {schema}."{table}" TO {mra_datagis_user};
'''


INSERT_INTO = '''
INSERT INTO {schema}."{table}" ({attrs_name}, {the_geom})
VALUES ({attrs_value}, ST_Transform({geom}, {to_epsg}));'''


def handle_ogr_field_type(k, n=None, p=None):

    if k.startswith('OFTString') and not n:
        k = k.replace(k, 'OFTWide')

    return {
        'OFTInteger': 'integer',
        'OFTIntegerList': 'integer[]',
        'OFTReal': 'double precision',  # numeric({n}, {p})
        'OFTRealList': 'double precision[]',  # numeric({n}, {p})[]
        'OFTString': 'varchar({n})',
        'OFTStringList': 'varchar({n})[]',
        'OFTWideString': 'text',
        'OFTWideStringList': 'text[]',
        'OFTBinary': 'bytea',
        'OFTDate': 'date',
        'OFTTime': 'time',
        'OFTDateTime': 'timestamp',
        'OFTInteger64': 'integer',
        'OFTInteger64List': 'integer[]'}.get(k, 'text').format(n=n, p=p)


def handle_ogr_geom_type(ogr_geom_type):
    return {
        'geometrycollection25d': 'GeometryCollectionZ',
        'linestring25d': 'LineStringZ',
        'multilinestring25d': 'MultiLineStringZ',
        'multipoint25d': 'MultiPointZ',
        'multipolygon25d': 'MultiPolygonZ',
        'point25d': 'PointZ',
        'polygon25d': 'PolygonZ'
        }.get(ogr_geom_type.name.lower(), ogr_geom_type.name)  # 'Geometry')


def get_epsg(obj):
    if obj.srs:
        try:
            epsg = obj.srs.identify_epsg()
        except SRSException:
            epsg = None
        if not epsg:
            if obj.srs.projected \
                    and obj.srs.auth_name('PROJCS') == 'EPSG':
                epsg = obj.srs.auth_code('PROJCS')
            if obj.srs.geographic \
                    and obj.srs.auth_name('GEOGCS') == 'EPSG':
                epsg = obj.srs.auth_code('GEOGCS')
        if not epsg:
            epsg = retreive_epsg_through_proj4(obj.srs.proj4)
        if not epsg:
            epsg = retreive_epsg_through_regex(obj.srs.name)
    if not epsg:
        raise NotFoundSrsError('SRS Not found')
    return epsg


def gdalinfo(cs, update={}):

    p = Path(cs.name)
    layername = slugify(p.name[:-len(p.suffix)]).replace('-', '_')
    table_id = update.get(
        layername, '{0}_{1}'.format(layername, str(uuid4())[:7]))
    xmin, ymin, xmax, ymax = cs.extent

    return {
        'id': table_id,
        'epsg': get_epsg(cs),
        'extent': ((xmin, ymin), (xmax, ymax))}


def ogr2postgis(ds, epsg=None, limit_to=1, update={}, filename=None, encoding='utf-8'):
    sql = []
    tables = []

    layers = ds.get_layers()
    if len(layers) > limit_to:
        raise ExceedsMaximumLayerNumberFixedError(
            count=len(layers), maximum=limit_to)
    layers.encoding = encoding
    # else:
    for layer in layers:
        layername = slugify(layer.name)

        if layername == 'ogrgeojson':
            p = Path(ds._datastore.name)
            layername = slugify(p.name[:-len(p.suffix)]).replace('-', '_')

        if epsg and is_valid_epsg(epsg):
            pass
        else:
            epsg = get_epsg(layer)

        SupportedCrs = apps.get_model(
            app_label='idgo_admin', model_name='SupportedCrs')

        try:
            SupportedCrs.objects.get(auth_name='EPSG', auth_code=epsg)
        except SupportedCrs.DoesNotExist:
            raise NotSupportedSrsError('SRS Not Supported')

        table_id = update.get(
            layername, '{0}_{1}'.format(layername, str(uuid4())[:7]))
        tables.append({'id': table_id, 'epsg': epsg})

        attrs = {}
        for i, k in enumerate(layer.fields):
            t = handle_ogr_field_type(
                layer.field_types[i].__qualname__,
                n=layer.field_widths[i],
                p=layer.field_precisions[i])
            attrs[k] = t

        # Erreur dans Django
        # Lorsqu'un 'layer' est composé de 'feature' de géométrie différente,
        # `ft.geom.__class__.__qualname__ == feat.geom_type.name is False`
        #
        #       > django/contrib/gis/gdal/feature.py
        #       @property
        #       def geom_type(self):
        #           "Return the OGR Geometry Type for this Feture."
        #           return OGRGeomType(capi.get_fd_geom_type(self._layer._ldefn))
        #
        # La fonction est incorrecte puisqu'elle se base sur le 'layer' et non
        # sur le 'feature'
        #
        # Donc dans ce cas on définit le type de géométrie de la couche
        # comme générique (soit 'Geometry')
        # Mais ceci est moche :
        test = set(feat.geom.__class__.__qualname__ for feat in layer)
        if test == {'Polygon', 'MultiPolygon'}:
            geometry = 'MultiPolygon'
        elif test == {'Polygon25D', 'MultiPolygon25D'}:
            geometry = 'MultiPolygon25D'
        elif test == {'LineString', 'MultiLineString'}:
            geometry = 'MultiLineString'
        elif test == {'LineString25D', 'MultiLineString25D'}:
            geometry = 'MultiLineString25D'
        elif test == {'Point', 'MultiPoint'}:
            geometry = 'MultiPoint'
        elif test == {'Point25D', 'MultiPoint25D'}:
            geometry = 'MultiPoint25D'
        else:
            geometry = len(test) > 1 \
                and 'Geometry' or handle_ogr_geom_type(layer.geom_type)

        sql.append(CREATE_TABLE.format(
            attrs=',\n  '.join(
                ['"{}" {}'.format(k, v) for k, v in attrs.items()]),
            description=layer.name,
            epsg=epsg,
            geometry=geometry,
            owner=OWNER,
            mra_datagis_user=MRA_DATAGIS_USER,
            schema=SCHEMA,
            table=str(table_id),
            the_geom=THE_GEOM,
            to_epsg=TO_EPSG))

        for feature in layer:
            attrs = {}
            for field in feature.fields:
                k = field.decode()
                try:
                    v = feature.get(k)
                except DjangoUnicodeDecodeError as e:
                    raise DataDecodingError()
                if isinstance(v, type(None)):
                    attrs[k] = 'null'
                elif isinstance(v, (datetime.date, datetime.time, datetime.datetime)):
                    attrs[k] = "'{}'".format(v.isoformat())
                elif isinstance(v, str):
                    attrs[k] = "'{}'".format(v.replace("'", "''"))
                else:
                    attrs[k] = "{}".format(v)

            if geometry.startswith('Multi'):
                geom = "ST_Multi(ST_GeomFromtext('{wkt}', {epsg}))"
            else:
                geom = "ST_GeomFromtext('{wkt}', {epsg})"

            sql.append(INSERT_INTO.format(
                attrs_name=', '.join(['"{}"'.format(x) for x in attrs.keys()]),
                attrs_value=', '.join(attrs.values()),
                geom=geom.format(epsg=epsg, wkt=feature.geom),
                owner=OWNER,
                schema=SCHEMA,
                table=str(table_id),
                the_geom=THE_GEOM,
                to_epsg=TO_EPSG))

    for table_id in update.values():
        rename_table(table_id, '__{}'.format(table_id))

    with connections[DATABASE].cursor() as cursor:
        for q in sql:
            try:
                cursor.execute(q)
            except Exception as e:
                # Revenir à l'état initial
                for table_id in [table['id'] for table in tables]:
                    drop_table(table_id)
                for table_id in update.values():
                    rename_table('__{}'.format(table_id), table_id)
                # Puis retourner l'erreur
                raise SQLError(e.__str__())

    for table_id in update.values():
        drop_table('__{}'.format(table_id))

    return tables


def get_extent(tables, schema='public'):
    if not tables:
        return None

    sub = 'SELECT {the_geom} as the_geom FROM {schema}."{table}"'
    sql = 'WITH all_geoms AS ({}) SELECT geometry(ST_Extent(the_geom)) FROM all_geoms;'.format(
        ' UNION '.join([
            sub.format(table=table, the_geom=THE_GEOM, schema=schema)
            for table in tables]))

    with connections[DATABASE].cursor() as cursor:
        try:
            cursor.execute(sql)
        except Exception as e:
            if e.__class__.__qualname__ != 'ProgrammingError':
                raise e
        records = cursor.fetchall()
        cursor.close()
    try:
        return records[0][0]
    except Exception:
        return None


def get_description(table, schema='public'):

    sql = '''
SELECT description FROM pg_description
JOIN pg_class ON pg_description.objoid = pg_class.oid
JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
WHERE relname = '{table}' AND nspname = '{schema}';
'''.format(table=table, schema=schema)

    with connections[DATABASE].cursor() as cursor:
        try:
            cursor.execute(sql)
        except Exception as e:
            if e.__class__.__qualname__ != 'ProgrammingError':
                raise e
        records = cursor.fetchall()
        cursor.close()
    try:
        return records[0][0]
    except Exception:
        return None


def rename_table(table, name, schema=SCHEMA):

    sql = '''
ALTER TABLE IF EXISTS "{table}" RENAME TO "{name}";
ALTER INDEX IF EXISTS "{table}_pkey" RENAME TO "{name}_pkey";
ALTER INDEX IF EXISTS "{table}_fid" RENAME TO "{name}_fid";
ALTER INDEX IF EXISTS "{table}_gix" RENAME TO "{name}_gix";
'''.format(schema=schema, table=table, name=name)

    with connections[DATABASE].cursor() as cursor:
        try:
            cursor.execute(sql)
        except Exception as e:
            if e.__class__.__qualname__ != 'ProgrammingError':
                raise e
        cursor.close()


def drop_table(table, schema=SCHEMA):
    sql = 'DROP TABLE {schema}."{table}";'.format(schema=schema, table=table)
    with connections[DATABASE].cursor() as cursor:
        try:
            cursor.execute(sql)
        except Exception as e:
            if e.__class__.__qualname__ != 'ProgrammingError':
                raise e
        cursor.close()
