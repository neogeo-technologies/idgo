# Copyright (c) 2017-2019 Datasud.
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


from django.core.management.base import BaseCommand
from django.utils import timezone
from idgo_admin.models import Resource
from idgo_admin.models import Task

import logging

NOW = timezone.now()
logger = logging.getLogger('django')


class Command(BaseCommand):

    help = """Synchroniser les ressources en fonction de la fréquence de
              mise à jour de chacune (pour celles dont le champ 'dl_url'
              est renseigné).
              * * * * * source ~/bin/activate; python manage.py sync_resources_temp -f minutly
              0 1 * * * source ~/bin/activate; python manage.py sync_resources_temp -f daily
              0 2 * * 1 source ~/bin/activate; python manage.py sync_resources_temp -f weekly
              0 3 1,15 * * source ~/bin/activate; python manage.py sync_resources_temp -f bimonthly
              0 3 1 * * source ~/bin/activate; python manage.py sync_resources_temp -f monthly
              0 4 1 1,4,7,10 * source ~/bin/activate; python manage.py sync_resources_temp -f quarterly
              0 5 1 1,7 * source ~/bin/activate; python manage.py sync_resources_temp -f biannual
              0 5 1 1 * source ~/bin/activate; python manage.py sync_resources_temp -f annual

              La meme fonction pourrai etre appelé pour les taches en erreur
              """

    def add_arguments(self, parser):
        parser.add_argument(
            "-f", "--freq",
            dest="freq", action="store", default="daily",
            help="Délai de synchronisation des ressources "
                 "choix possibles: daily, daily, weekly, bimonthly, monthly, "
                 "quarterly, biannual, annual [default: daily]")

        parser.add_argument(
            "-r", "--retry",
            dest="retry", action="store", default=False, type=bool,
            help="Délai de synchronisation des ressources "
                 "choix possibles: daily, daily, weekly, bimonthly, monthly, "
                 "quarterly, biannual, annual [default: daily]")

    def tasks_creator(self, resources):
        for resource in resources:
            extras = {
                'dataset': resource.dataset.id,
                'resource': resource.id
            }

            task = Task.objects.create(action=__name__)
            try:
                resource.save(current_user=None, synchronize=True)
            except Exception as e:
                task.extras = {**extras, **{'error': e.__str__()}}
                task.state = 'failed'
            else:
                task.extras = extras
                task.state = 'succesful'
            finally:
                task.end = timezone.now()
                task.save()

    def handle(self, *args, **options):

        freq = options.get('freq')
        retry = options.get('retry', False)

        logger.error(
            "CRON CALL '{}' test".format(freq)
        )

        if freq == 'daily':
            logger.error(
                "CRON CALL '{}' raise exception".format(freq)
            )
            raise Exception('haha')

        if not any(freq in frq for frq in Resource.FREQUENCY_CHOICES):
            logger.error(
                "Le delai de synchronisation '{}' n'est pas défini parmi les choix possibles".format(freq)
            )
            return

        # Ajout d'un control pour freq = never si necessaire
        if freq == 'never':
            logger.error(
                "Le delai de synchronisation '{}' n'a pas besoin d'etre traité".format(freq)
            )
            return

        if not retry:
            resources = Resource.objects.exclude(dl_url=None).filter(
                synchronisation=True, sync_frequency=freq
            )
            logger.info(
                "La synchronisation de type '{}' doit traiter {} ressource(s)".format(
                    freq, resources.count())
            )
            # self.tasks_creator(resources)

        # On pourrai rappelé en continue des creation de tache qui on échouée?
        # Ou alors définir une action spécifique pour les taches en échecs
        else:
            tasks = Task.objects.filter(state='failed')
            resources = Resource.objects.exclude(dl_url=None).filter(
                pk__in=[t.extras.get('resource', None) for t in tasks],
                synchronisation=True, sync_frequency=freq
            )
            # self.tasks_creator(resources)
