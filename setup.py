from setuptools import find_packages, setup

with open('README.md', 'r') as fh:
    long_description = fh.read()

requirements = (
    'Django>=1.11,<4.0',
    'djangorestframework>=3.0,<4.0',
    'setuptools',
)

dev_requirements = (
    'pytest',
)

setup(
    name='django-requestlogs',
    zip_safe=False,
    version='0.2.4',
    description='Audit logging for Django and Django Rest Framework',
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[],
    keywords=['django', 'log', 'logging'],
    author='Teemu Husso',
    author_email='teemu.husso@gmail.com',
    url='https://github.com/Raekkeri/django-requestlogs',
    download_url='https://github.com/raekkeri/django-requestlogs/tarball/0.1',
    packages=find_packages(exclude=['tests']),
    install_requires=requirements,
    extras_require={
        'dev': dev_requirements
    },
)
