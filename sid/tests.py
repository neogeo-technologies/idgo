# Copyright (c) 2019 Neogeo-Technologies.
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


import logging
from pprint import pformat

from django.test import tag
from django.urls import reverse
from rest_framework.test import APITransactionTestCase

from idgo_admin.models import Organisation
from idgo_admin.models import Profile


logger = logging.getLogger('sid.tests')


class RootTestCase(APITransactionTestCase):
    create_xml_path = ''
    put_create_xml_path = ''
    update_xml_path = ''
    create_url_path = ''
    update_url_path = ''
    sid_id = ''
    sid_id_pust = ''
    queryset = None

    def test_create(self):
        with open(self.create_xml_path) as fp:
            r = self.client.post(
                reverse(self.create_url_path),
                data=fp.read(),
                content_type='application/xml',
            )

            self.assertEqual(r.status_code, 201)
            self.assertEqual(self.queryset.filter(sid_id=self.sid_id).count(), 1)

    def test_create_update(self):

        with open(self.create_xml_path) as fp:
            d = {'file': fp}

            r = self.client.post(
                reverse(self.create_url_path),
                data=d,
            )

            self.assertEqual(r.status_code, 201)
            self.assertEqual(self.queryset.all().count(), 1)

        logger.info(
            pformat(self.queryset.get(sid_id=self.sid_id).__dict__)
        )

        with open(self.update_xml_path) as fp2:
            d = {'file': fp2}

            r = self.client.put(
                reverse(self.update_url_path, kwargs={'sid_id': self.sid_id}),
                data=fp2.read(),
                content_type='application/xml',
            )

            logger.info(
                pformat(self.queryset.get(sid_id=self.sid_id).__dict__)
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.queryset.all().count(), 1)

    def test_pust(self):
        """
        On test la création d'orga & company & employee & agent à travers un PUT
        """

        with open(self.put_create_xml_path) as fp2:
            d = {'file': fp2}
            r = self.client.put(
                reverse(
                    self.update_url_path,
                    kwargs={'sid_id': self.sid_id_pust}
                ),
                data=fp2.read(),
                content_type='application/xml',
            )
            logger.info(
                pformat(self.queryset.get(sid_id=self.sid_id_pust).__dict__)
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.queryset.all().count(), 1)


class TestOrganism(RootTestCase):

    create_xml_path = 'data/organism.xml'
    put_create_xml_path = 'data/organism_pust.xml'
    update_xml_path = 'data/organism_update1.xml'
    create_url_path = 'sid:organism-list'
    update_url_path = 'sid:organism-detail'
    sid_id = '294680'
    sid_id_pust = '123456789'
    queryset = Organisation.objects.all()


class TestCompany(RootTestCase):

    create_xml_path = 'data/company.xml'
    put_create_xml_path = 'data/company_pust.xml'
    update_xml_path = 'data/company_update1.xml'
    create_url_path = 'sid:company-list'
    update_url_path = 'sid:company-detail'
    sid_id = '294679'
    sid_id_pust = '123456789'
    queryset = Organisation.objects.all()


class TestAgent(RootTestCase):
    fixtures = [
        'data/license.json',
        'data/organisation_type.json',
        'data/organisation.json',
    ]
    create_xml_path = 'data/agent.xml'
    update_xml_path = 'data/agent_update1.xml'
    put_create_xml_path = 'data/agent_pust.xml'
    create_url_path = 'sid:agent-list'
    update_url_path = 'sid:agent-detail'
    sid_id = '307164'
    sid_id_pust = '123456789'
    queryset = Profile.objects.all()


@tag('selected')
class TestEmployee(RootTestCase):
    fixtures = [
        'data/license.json',
        'data/organisation_type.json',
        'data/organisation.json',
    ]
    create_xml_path = 'data/employee.xml'
    put_create_xml_path = 'data/employee_pust.xml'
    update_xml_path = 'data/employee_update1.xml'
    create_url_path = 'sid:employee-list'
    update_url_path = 'sid:employee-detail'
    sid_id = '307163'
    sid_id_pust = '123456789'
    queryset = Profile.objects.all()
