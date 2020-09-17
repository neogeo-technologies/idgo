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


import os.path
from setuptools import find_packages
from setuptools import setup


version = '1.3.5'


def parse_requirements(filename):
    with open(filename) as f:
        lines = (line.strip() for line in f)
        return [line for line in lines if line and not line.startswith('#')]


dirname = os.path.dirname(__file__)
reqs_filename = os.path.join(dirname, 'requirements.txt')

reqs = [str(req) for req in parse_requirements(reqs_filename)]

setup(
    name='idgo',
    version=version,
    description='IDGO',
    author='Neogeo Technologies',
    author_email='contact@neogeo.fr',
    url='https://git.neogeo.fr/idgo/apps/idgo',
    license='Apache License, Version 2.0',
    classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    packages=find_packages(where='.'),
    install_requires=reqs,
)
