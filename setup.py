from setuptools import setup, find_packages


def get_requirements():
    with open('requirements.txt') as req_file:
        reqs = req_file.readlines()
    return [req for req in reqs if not req.startswith('-e')]


setup(
    descrtiption="Site d'administration d'IDGO",
    packages=find_packages(),
    long_description=open('README.md').read(),
    url='https://github.com/neogeo-technologies/idgo',
    install_requires=get_requirements()
)
