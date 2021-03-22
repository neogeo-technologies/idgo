# Copyright (c) 2017-2021 Neogeo-Technologies.
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


import csv
from dateutil.relativedelta import relativedelta
from io import StringIO
import json
from uuid import UUID

from celeriac.apps import app as celery_app
from celeriac.models import TaskTracking
from celery.signals import before_task_publish
from celery.signals import task_postrun
from celery.utils.log import get_task_logger

from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.utils import timezone

from idgo_admin.ckan_module import CkanHandler
from idgo_admin.ckan_module import CkanUserHandler
from idgo_admin.models import AccountActions
from idgo_admin.models import AsyncExtractorTask
from idgo_admin.models import Category
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Mail
from idgo_admin.models.mail import get_admins_mails
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.models import Task


RemoteCatalogs = []
from idgo_admin import ENABLE_CKAN_HARVESTER  # noqa
if ENABLE_CKAN_HARVESTER:
    from idgo_admin.models.organisation import RemoteCkan
    RemoteCatalogs.append(RemoteCkan)
from idgo_admin import ENABLE_CSW_HARVESTER  # noqa
if ENABLE_CSW_HARVESTER:
    from idgo_admin.models.organisation import RemoteCsw
    RemoteCatalogs.append(RemoteCsw)
from idgo_admin import ENABLE_DCAT_HARVESTER  # noqa
if ENABLE_DCAT_HARVESTER:
    from idgo_admin.models.organisation import RemoteDcat
    RemoteCatalogs.append(RemoteDcat)

from idgo_admin import DEFAULT_FROM_EMAIL
from idgo_admin import ENABLE_SENDING_MAIL
from idgo_admin import IDGO_ADMIN_HARVESTER_USER


logger = get_task_logger(__name__)


# Toutes les tâches celeriac génèrent une trace en base de données afin
# de suivre son état, nécessaire pour générer des rapports d'activité des
# synchronisations des ressources et des catalogues distants CKAN, CSW, DCAT.

@before_task_publish.connect
def on_beforehand(headers=None, body=None, sender=None, **kwargs):
    TaskTracking.objects.create(
        uuid=UUID(body.get('id')), task=body.get('task'), detail=body)


@task_postrun.connect
def on_task_postrun(state=None, task_id=None, task=None,
                    signal=None, sender=None, retval=None, **kwargs):
    ttracking = TaskTracking.objects.get(uuid=UUID(task_id))

    ttracking.state = {
        'UNKNOWN': 'unknown',
        'FAILURE': 'failed',
        'SUCCESS': 'succesful',
        }.get(state)

    if isinstance(retval, Exception):
        ttracking.detail = {**ttracking.detail, **{'error': retval.__str__()}}

    ttracking.end = timezone.now()
    ttracking.save()


# =====================
# DÉFINITION DES TÂCHES
# =====================


@celery_app.task()
def clean_tasktracking_table(*args, **kwargs):
    """Supprimer des objets de la table TaskTracking."""

    TaskTracking.objects.filter(**kwargs).delete()


@celery_app.task()
def save_resource(*args, pk=None, **kwargs):
    """Sauvegarder une resource."""

    resource = Resource.objects.get(pk=pk)
    resource.save(current_user=None, synchronize=True)


@celery_app.task()
def sync_resources(*args, **kwargs):
    """Synchroniser les tâches d'extraction."""

    resources = Resource.objects.filter(synchronisation=True, **kwargs)
    logger.info(
        "Synchronize %s >> %s" % (
            str(kwargs), str([(r.pk, r.dataset.pk) for r in resources])
            )
        )
    for resource in resources:
        save_resource.apply_async(kwargs={'pk': resource.pk})


@celery_app.task()
def sync_categories():
    """Synchroniser les catégories avec CKAN."""

    for category in Category.objects.all():
        if not CkanHandler.is_group_exists(category.slug):
            CkanHandler.add_group(category)


@celery_app.task()
def sync_extractor_tasks():
    """Synchroniser les tâches d'extraction."""

    for instance in AsyncExtractorTask.objects.filter(success=None):
        logger.info("Check extractor task: %s" % str(instance.uuid))


@celery_app.task()
def sync_remote_catalogs(*args, **kwargs):
    """Synchroniser les catalogues distants."""

    for RemoteCatalog in RemoteCatalogs:
        for remote in RemoteCatalog.objects.filter(**kwargs):
            logger.info("Start synchronize remote instance %s %d (%s)" % (
                remote.__class__.__qualname__, remote.pk, remote.url))
            try:
                remote.save()
            except Exception as e:
                logger.exception(e)


@celery_app.task()
def sync_ckan_allowed_users_by_resource(*args, **kwargs):
    """Synchroniser `ckan-restricted` pour le cas particuliers
    des autorisations par organisation.
    """

    def get_all_users_for_organisations(organisation__in):
        filter = {'organisation__in': organisation__in,
                  'organisation__is_active': True}
        return [profile.user.username
                for profile in Profile.objects.filter(**filter)]

    for resource in Resource.objects.exclude(organisations_allowed=None):
        dataset = resource.dataset

        organisation__in = [r.pk for r in resource.organisations_allowed.all()]
        allowed_users = get_all_users_for_organisations(organisation__in)
        restricted = {
            'allowed_users': ','.join(allowed_users),
            'level': 'only_allowed_users'}

        ckan_params = {
            'id': str(resource.ckan_id),
            'restricted': json.dumps(restricted)}

        logger.info("Update 'restricted' for Resource '%d'" % resource.pk)

        apikey = CkanHandler.get_user(dataset.editor.username)['apikey']
        with CkanUserHandler(apikey=apikey) as ckan:
            try:
                package = ckan.get_package(str(dataset.ckan_id))
                ckan.push_resource(package, **ckan_params)
            except Exception as e:
                logger.exception(e)
                logger.info("Continue...")


@celery_app.task()
def check_resources_last_update(*args, **kwargs):

    csv_data = [('dataset_slug',
                 'resource_uuid',
                 'sync_frequency',
                 'last_update',
                 'delay')]

    for resource in Resource.objects.filter(**kwargs):
        delta = {
            # '5mn': relativedelta(minutes=5),
            # '15mn': relativedelta(minutes=15),
            # '20mn': relativedelta(minutes=20),
            # '30mn': relativedelta(minutes=30),
            '1hour': relativedelta(hours=1),
            '3hours': relativedelta(hours=3),
            '6hours': relativedelta(hours=6),
            'daily': relativedelta(days=1),
            'weekly': relativedelta(days=7),
            'bimonthly': relativedelta(days=15),
            'monthly': relativedelta(months=1),
            'quarterly': relativedelta(months=3),
            'biannual': relativedelta(months=6),
            'annual': relativedelta(year=1),
            }.get(resource.sync_frequency)
        if not delta:
            continue
        delay = timezone.now() - (resource.last_update + delta)
        if delay.total_seconds() > 0:
            csv_data.append((
                resource.dataset.slug,
                resource.ckan_id,
                resource.sync_frequency,
                resource.last_update,
                delay,
                ))

    if not csv_data:  # Nothing to do
        return

    f = StringIO()
    csv.writer(f).writerows(csv_data)

    mail_instance = Mail.objects.get(template_name='resources_update_with_delay')

    mail = EmailMessage(
        mail_instance.subject,
        mail_instance.message,
        DEFAULT_FROM_EMAIL,
        get_admins_mails())
    mail.attach('log.csv', f.getvalue(), 'text/csv')

    if ENABLE_SENDING_MAIL:
        try:
            mail.send()
        except SMTPDataError as e:
            logger.error(e)
            # Activer l'exception lorsque gérée par l'application.
            # return MailError()
    else:
        logger.warning("Sending mail is disable.")


@celery_app.task()
def send_sync_report_mail(*args, **kwargs):
    """Envoyer un e-mail contenant les dernières Tasks exécutées ;
    par exemple suite un une synchronisation des ressources exécutée
    avec le script `sync_resources`.
    """

    tasks_tracking = TaskTracking.objects.filter(
        task='celeriac.tasks.save_resource',
        start__gte=timezone.datetime.today().date(),
        end__isnull=False,
        )

    csv_data = [('state',
                 'starting',
                 'end',
                 'dataset_id',
                 'dataset_name',
                 'resource_id',
                 'resource_name',
                 'error')]

    for task_tracking in tasks_tracking:
        try:
            resource = Resource.objects.get(pk=task_tracking.detail['kwargs']['pk'])
        except KeyError as e:
            logger.error("Malformed JSON: please check instance TaskTracking '%d'" % task_tracking.pk)
            logger.warning("Error was ignored.")
            continue
        except Resource.DoesNotExist as e:
            logger.exception(e)
            logger.warning("Error was ignored.")
            continue
        # else:
        csv_data.append((
            task_tracking.state,
            task_tracking.start.isoformat(),
            task_tracking.end.isoformat(),
            resource.dataset.id,
            resource.dataset.title,
            resource.id,
            resource.title,
            task_tracking.detail.get('error', None),
            ))

    f = StringIO()
    csv.writer(f).writerows(csv_data)

    mail_instance = Mail.objects.get(template_name='email_task')

    mail = EmailMessage(
        mail_instance.subject,
        mail_instance.message,
        DEFAULT_FROM_EMAIL,
        get_admins_mails())
    mail.attach('log.csv', f.getvalue(), 'text/csv')

    if ENABLE_SENDING_MAIL:
        try:
            mail.send()
        except SMTPDataError as e:
            logger.error(e)
            # Activer l'exception lorsque gérée par l'application.
            # return MailError()
    else:
        logger.warning("Sending mail is disable.")


@celery_app.task()
def clean_up_actions_out_of_delay(*args, **kwargs):

    def n_days_ago(days):
        return timezone.now() - timezone.timedelta(days=days)

    organisations_to_delete = []
    profiles_to_delete = []

    old_actions = AccountActions.objects.filter(
        closed=None, created_on__lte=n_days_ago(2))

    for action in old_actions:
        username = 'N/A'
        org_name = 'N/A'

        if action.profile.user:
            username = action.profile.user.username

        if action.profile.organisation:
            org_name = action.profile.organisation.legal_name

        # if action.action == 'reset_password':
        #     pass TODO ?

        # if action.action == 'confirm_rattachement':
        #     pass TODO ?

        if action.action == 'confirm_mail':
            profiles_to_delete.append(action.profile)

        if action.action == 'confirm_new_organisation':
            organisations_to_delete.append(action.profile.organisation)

        if action.action == 'confirm_contribution':
            try:
                liaison = LiaisonsContributeurs.objects.get(
                    profile=action.profile,
                    organisation=action.organisation)
            except LiaisonsContributeurs.DoesNotExist as e:
                logger.exception(e)
                logger.info("Pass...")
            else:
                liaison.delete()
                logger.info("Delete LiaisonsContributeurs: %s / %s" % (
                    username, action.organisation.legal_name))

        if action.action == 'confirm_referent':
            try:
                liaison = LiaisonsReferents.objects.get(
                    profile=action.profile, organisation=action.organisation)
            except LiaisonsContributeurs.DoesNotExist as e:
                logger.exception(e)
                logger.info("Pass...")
            else:
                liaison.delete()
                logger.info("Delete LiaisonsReferents: %s / %s" % (
                    username, action.organisation.legal_name))

        action.delete()

    # Fait en second pour ne pas 'casser' la boucle précédente à cause des cascade_on_delete
    for profile in profiles_to_delete:
        profile.delete()
        user.delete()
        logger.info("Delete User/Profile: %s" % profile.user.username)

    for organisation in organisations_to_delete:
        organisation.delete()
        logger.info("Delete Organisation %s" % organisation.name)