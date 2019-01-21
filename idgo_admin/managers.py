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


from django.apps import apps
from django.contrib.gis.db import models
from django.utils import timezone
from idgo_admin.models import get_super_editor
from idgo_admin.utils import clean_my_obj


class DefaultDatasetManager(models.Manager):

    def create(self, **kwargs):
        save_opts = kwargs.pop('save_opts', {})
        obj = self.model(**kwargs)
        self._for_write = True
        obj.save(force_insert=True, using=self.db, **save_opts)
        return obj

    def get(self, **kwargs):
        return super().get(**kwargs)


class HarvestedDataset(models.Manager):

    def create(self, **kwargs):
        remote_ckan = kwargs.pop('remote_ckan', None)
        remote_dataset = kwargs.pop('remote_dataset', None)
        remote_organisation = kwargs.pop('remote_organisation', None)

        save_opts = {'editor': get_super_editor(), 'synchronize': False}
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        dataset = Dataset.default.create(save_opts=save_opts, **kwargs)

        DataType = apps.get_model(app_label='idgo_admin', model_name='DataType')
        dataset.data_type = DataType.objects.filter(ckan_slug='donnees-moissonnees')
        dataset.save(editor=get_super_editor(), synchronize=True)

        RemoteCkanDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')

        RemoteCkanDataset.objects.create(
            created_by=dataset.editor,
            dataset=dataset,
            remote_ckan=remote_ckan,
            remote_dataset=remote_dataset,
            remote_organisation=remote_organisation)

        return dataset

    def filter(self, **kwargs):
        kvp = clean_my_obj({
            'remote_ckan': kwargs.pop('remote_ckan', None),
            'remote_dataset': kwargs.pop('remote_dataset', None),
            'remote_organisation': kwargs.pop('remote_organisation', None),
            'remote_organisation__in': kwargs.pop('remote_organisation__in', None)})

        if kvp:
            Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
            RemoteCkanDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')

            return Dataset.objects.filter(id__in=[
                entry.dataset.id for entry in RemoteCkanDataset.objects.filter(**kvp)])

        return super().filter(**kwargs)

    def get(self, **kwargs):

        remote_dataset = kwargs.pop('remote_dataset', None)
        if remote_dataset:
            RemoteCkanDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
            return RemoteCkanDataset.objects.get(remote_dataset=remote_dataset).dataset

        return super().get(**kwargs)

    def get_queryset(self, **kwargs):
        Dataset = apps.get_model(app_label='idgo_admin', model_name='Dataset')
        RemoteCkanDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
        return Dataset.objects.filter(
            id__in=[entry.dataset.id for entry in RemoteCkanDataset.objects.all()])

    def update_or_create(self, **kwargs):
        RemoteCkanDataset = apps.get_model(app_label='idgo_admin', model_name='RemoteCkanDataset')
        remote_dataset = kwargs.get('remote_dataset', None)
        try:
            instance = self.get(remote_dataset=remote_dataset)
        except RemoteCkanDataset.DoesNotExist:
            instance = self.create(**kwargs)
            created = True
        else:
            created = False
            harvested = RemoteCkanDataset.objects.get(dataset=instance.id)
            harvested.updated_on = timezone.now()
            harvested.remote_organisation = kwargs.pop('remote_organisation', None)
            harvested.save()

            for k, v in kwargs.items():
                setattr(instance, k, v)
            instance.save()

        return instance, created
