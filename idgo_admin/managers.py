# Copyright (c) 2017-2020 Neogeo-Technologies.
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


from idgo_admin.utils import clean_my_obj
from itertools import chain

from django.apps import apps
from django.contrib.gis.db import models
from django.utils import timezone

from idgo_admin import DEFAULTS_VALUES


COMMUNES_REGEX = DEFAULTS_VALUES.get('COMMUNES_REGEX', '^\d(\d|A|B)\d{3}$')


# =========================================================
# Définition de Managers pour les jeux de données (Dataset)
# =========================================================


class DefaultDatasetManager(models.Manager):

    def create(self, **kwargs):
        save_opts = kwargs.pop('save_opts', {})
        obj = self.model(**kwargs)
        self._for_write = True
        obj.save(force_insert=True, using=self.db, **save_opts)
        return obj

    def get_queryset(self, **kwargs):
        exclude_pk = []

        if ENABLE_CKAN_HARVESTER:
            RemoteCkanDataset = apps.get_model(
                app_label='idgo_admin', model_name='RemoteCkanDataset')
            exclude_pk.append(
                RemoteCkanDataset.objects.all().values_list('dataset__pk', flat=True))

        if ENABLE_CSW_HARVESTER:
            RemoteCswDataset = apps.get_model(
                app_label='idgo_admin', model_name='RemoteCswDataset')
            exclude_pk.append(
                RemoteCswDataset.objects.all().values_list('dataset__pk', flat=True))

        if ENABLE_DCAT_HARVESTER:
            RemoteDcatDataset = apps.get_model(
                app_label='idgo_admin', model_name='RemoteDcatDataset')
            exclude_pk.append(
                RemoteDcatDataset.objects.all().values_list('dataset__pk', flat=True))

        return super().get_queryset(**kwargs).exclude(pk__in=list(chain(*exclude_pk)))

    def all(self):
        return self.get_queryset()

    def get(self, **kwargs):
        return super().get(**kwargs)


from idgo_admin import ENABLE_CKAN_HARVESTER  # noqa
if ENABLE_CKAN_HARVESTER:

    class HarvestedCkanDatasetManager(models.Manager):

        def create(self, **kwargs):
            remote_instance = kwargs.pop('remote_instance', None)
            remote_dataset = kwargs.pop('remote_dataset', None)
            remote_organisation = kwargs.pop('remote_organisation', None)

            # Dans un premier temps on crée le jeu de données sans le synchroniser à CKAN
            Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
            save_opts = {'current_user': None, 'synchronize': False}
            dataset = Dataset.default.create(save_opts=save_opts, **kwargs)

            # Puis on crée la liaison avec le CKAN distant
            RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
            RemoteDataset.objects.create(
                created_by=dataset.editor,
                dataset=dataset,
                remote_instance=remote_instance,
                remote_dataset=remote_dataset,
                remote_organisation=remote_organisation,
                )

            # Enfin on met à jour le jeu de données et on le synchronize avec CKAN
            DataType = apps.get_model(app_label='idgo_admin', model_name='DataType')
            dataset.data_type = DataType.objects.filter(slug='donnees-moissonnees')
            dataset.save(current_user=None, synchronize=True)

            return dataset

        def filter(self, **kwargs):
            remote_instance = kwargs.pop('remote_instance', None)
            remote_dataset = kwargs.pop('remote_dataset', None)
            remote_organisation = kwargs.pop('remote_organisation', None)
            remote_organisation__in = kwargs.pop('remote_organisation__in', None)

            kvp = clean_my_obj({
                'remote_instance': remote_instance,
                'remote_dataset': remote_dataset,
                'remote_organisation': remote_organisation,
                'remote_organisation__in': remote_organisation__in,
                })
            if kvp:
                Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
                RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')

                return Dataset.objects.filter(id__in=[
                    entry.dataset.id for entry in RemoteDataset.objects.filter(**kvp)])

            return super().filter(**kwargs)

        def get(self, **kwargs):
            remote_dataset = kwargs.pop('remote_dataset', None)

            if remote_dataset:
                RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
                return RemoteDataset.objects.get(remote_dataset=remote_dataset).dataset

            return super().get(**kwargs)

        def get_queryset(self, **kwargs):
            Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
            RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
            return Dataset.objects.filter(
                id__in=[entry.dataset.id for entry in RemoteDataset.objects.all()])

        def update_or_create(self, **kwargs):
            remote_dataset = kwargs.get('remote_dataset', None)

            RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
            try:
                dataset = self.get(remote_dataset=remote_dataset)
            except RemoteDataset.DoesNotExist:
                dataset = self.create(**kwargs)
                created = True
            else:
                created = False
                harvested = RemoteDataset.objects.get(dataset=dataset)
                harvested.updated_on = timezone.now()
                harvested.remote_organisation = kwargs.pop('remote_organisation', None)
                harvested.save()

                for k, v in kwargs.items():
                    setattr(dataset, k, v)
                dataset.save(current_user=None, synchronize=True)

            return dataset, created


from idgo_admin import ENABLE_CSW_HARVESTER  # noqa
if ENABLE_CSW_HARVESTER:

    class HarvestedCswDatasetManager(models.Manager):

        def create(self, **kwargs):
            remote_instance = kwargs.pop('remote_instance', None)
            remote_dataset = kwargs.pop('remote_dataset', None)

            # Dans un premier temps on crée le jeu de données sans le synchroniser à CSW
            Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
            save_opts = {'current_user': None, 'synchronize': False}
            dataset = Dataset.default.create(save_opts=save_opts, **kwargs)

            # Puis on crée la liaison avec le CSW distant
            RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCswDataset')
            RemoteDataset.objects.create(
                created_by=dataset.editor,
                dataset=dataset,
                remote_instance=remote_instance,
                remote_dataset=remote_dataset,
                )

            # Enfin on met à jour le jeu de données et on le synchronize avec CSW
            DataType = apps.get_model(app_label='idgo_admin', model_name='DataType')
            dataset.data_type = DataType.objects.filter(slug='donnees-moissonnees')
            dataset.save(current_user=None, synchronize=True)

            return dataset

        def filter(self, **kwargs):
            remote_instance = kwargs.pop('remote_instance', None)
            remote_dataset = kwargs.pop('remote_dataset', None)

            kvp = clean_my_obj({
                'remote_instance': remote_instance,
                'remote_dataset': remote_dataset,
                })
            if kvp:
                Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
                RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCswDataset')

                return Dataset.objects.filter(id__in=[
                    entry.dataset.id for entry in RemoteDataset.objects.filter(**kvp)])

            return super().filter(**kwargs)

        def get(self, **kwargs):
            remote_dataset = kwargs.pop('remote_dataset', None)

            if remote_dataset:
                RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCswDataset')
                return RemoteDataset.objects.get(remote_dataset=remote_dataset).dataset

            return super().get(**kwargs)

        def get_queryset(self, **kwargs):
            Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
            RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCswDataset')
            return Dataset.objects.filter(
                id__in=[entry.dataset.id for entry in RemoteDataset.objects.all()])

        def update_or_create(self, **kwargs):
            remote_dataset = kwargs.get('remote_dataset', None)

            RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCswDataset')
            try:
                dataset = self.get(remote_dataset=remote_dataset)
            except RemoteDataset.DoesNotExist:
                dataset = self.create(**kwargs)
                created = True
            else:
                created = False
                harvested = RemoteDataset.objects.get(dataset=dataset)
                harvested.updated_on = timezone.now()
                # harvested.remote_organisation = kwargs.pop('remote_organisation', None)
                harvested.save()

                for k, v in kwargs.items():
                    setattr(dataset, k, v)
                dataset.save(current_user=None, synchronize=True)

            return dataset, created


from idgo_admin import ENABLE_DCAT_HARVESTER  # noqa
if ENABLE_DCAT_HARVESTER:

    class HarvestedDcatDatasetManager(models.Manager):

        def create(self, **kwargs):
            remote_instance = kwargs.pop('remote_instance', None)
            remote_dataset = kwargs.pop('remote_dataset', None)
            remote_organisation = kwargs.pop('remote_organisation', None)

            # Dans un premier temps on crée le jeu de données sans le synchroniser à DCAT
            Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
            save_opts = {'current_user': None, 'synchronize': False}
            dataset = Dataset.default.create(save_opts=save_opts, **kwargs)

            # Puis on crée la liaison avec le DCAT distant
            RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteDcatDataset')
            RemoteDataset.objects.create(
                created_by=dataset.editor,
                dataset=dataset,
                remote_instance=remote_instance,
                remote_dataset=remote_dataset,
                remote_organisation=remote_organisation,
                )

            # Enfin on met à jour le jeu de données et on le synchronize avec DCAT
            DataType = apps.get_model(app_label='idgo_admin', model_name='DataType')
            dataset.data_type = DataType.objects.filter(slug='donnees-moissonnees')
            dataset.save(current_user=None, synchronize=True)

            return dataset

        def filter(self, **kwargs):
            remote_instance = kwargs.pop('remote_instance', None)
            remote_dataset = kwargs.pop('remote_dataset', None)
            remote_organisation = kwargs.pop('remote_organisation', None)
            remote_organisation__in = kwargs.pop('remote_organisation__in', None)

            kvp = clean_my_obj({
                'remote_instance': remote_instance,
                'remote_dataset': remote_dataset,
                'remote_organisation': remote_organisation,
                'remote_organisation__in': remote_organisation__in,
                })
            if kvp:
                Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
                RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteDcatDataset')

                return Dataset.objects.filter(id__in=[
                    entry.dataset.id for entry in RemoteDataset.objects.filter(**kvp)])

            return super().filter(**kwargs)

        def get(self, **kwargs):
            remote_dataset = kwargs.pop('remote_dataset', None)

            if remote_dataset:
                RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteDcatDataset')
                return RemoteDataset.objects.get(remote_dataset=remote_dataset).dataset

            return super().get(**kwargs)

        def get_queryset(self, **kwargs):
            Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
            RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteDcatDataset')
            return Dataset.objects.filter(
                id__in=[entry.dataset.id for entry in RemoteDataset.objects.all()])

        def update_or_create(self, **kwargs):
            remote_dataset = kwargs.get('remote_dataset', None)

            RemoteDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteDcatDataset')
            try:
                dataset = self.get(remote_dataset=remote_dataset)
            except RemoteDataset.DoesNotExist:
                dataset = self.create(**kwargs)
                created = True
            else:
                created = False
                harvested = RemoteDataset.objects.get(dataset=dataset)
                harvested.updated_on = timezone.now()
                harvested.remote_organisation = kwargs.pop('remote_organisation', None)
                harvested.save()

                for k, v in kwargs.items():
                    setattr(dataset, k, v)
                dataset.save(current_user=None, synchronize=True)

            return dataset, created


# =====================================================
# Définition de Managers pour les ressources (Resource)
# =====================================================


class DefaultResourceManager(models.Manager):

    def create(self, **kwargs):
        save_opts = kwargs.pop('save_opts', {})
        obj = self.model(**kwargs)
        self._for_write = True
        obj.save(force_insert=True, using=self.db, **save_opts)
        return obj

    def get(self, **kwargs):
        return super().get(**kwargs)


# ====================================================
# Définition de Managers pour les couches SIG (Layers)
# ====================================================


class RasterLayerManager(models.Manager):

    def create(self, **kwargs):
        save_opts = kwargs.pop('save_opts', {})
        kwargs['type'] = 'raster'
        obj = self.model(**kwargs)
        self._for_write = True
        obj.save(force_insert=True, using=self.db, **save_opts)
        return obj

    def get(self, **kwargs):
        return super().get(**kwargs)


class VectorLayerManager(models.Manager):

    def create(self, **kwargs):
        save_opts = kwargs.pop('save_opts', {})
        kwargs['type'] = 'vector'
        obj = self.model(**kwargs)
        self._for_write = True
        obj.save(force_insert=True, using=self.db, **save_opts)
        return obj

    def get(self, **kwargs):
        return super().get(**kwargs)


# ========================================
# Définition de Managers pour les communes
# ========================================


class DefaultCommuneManager(models.GeoManager):

    def get_queryset(self, **kwargs):
        return super().get_queryset(**kwargs).filter(code__regex=COMMUNES_REGEX)

    def all(self):
        return self.get_queryset()

    def get(self, **kwargs):
        return super().get(**kwargs)


# =============================================
# Définition de Managers pour les organisations
# =============================================


class OrganisationManager(models.GeoManager):

    def get_queryset(self, **kwargs):
        return super().get_queryset(**kwargs)

    def get_contribs(self, profile):
        LiaisonsContributeurs = apps.get_model(
            app_label='idgo_admin', model_name='LiaisonsContributeurs')
        orga_pks = LiaisonsContributeurs.objects.filter(
            profile=profile, validated_on__isnull=False
        ).values_list('organisation__pk')

        return self.get_queryset().filter(pk__in=orga_pks)

    def get_subordinated_organisations(self, profile):
        qs = self.get_queryset().filter(is_active=True)
        if profile.is_admin:
            return qs

        LiaisonsReferents = apps.get_model(
            app_label='idgo_admin', model_name='LiaisonsReferents')
        orga_pks = LiaisonsReferents.objects.filter(
            profile=profile, validated_on__isnull=False
        ).values_list('organisation__pk')

        return qs.filter(pk__in=orga_pks)