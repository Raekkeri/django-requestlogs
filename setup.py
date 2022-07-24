from setuptools import find_packages, setup

with open('README.md', 'r') as fh:
    long_description = fh.read()

VERSION = '0.7.0'

requirements = (
    'Django>=1.11,<5.0',
    'djangorestframework>=3.0,<4.0',
    'setuptools',
)

dev_requirements = (
    'pytest',
)

setup(
    name='django-requestlogs',
    zip_safe=False,
    version=VERSION,
    description='Audit logging for Django and Django Rest Framework',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords=['django', 'log', 'logging'],
    author='Teemu Husso',
    author_email='teemu.husso@gmail.com',
    url='https://github.com/Raekkeri/django-requestlogs',
    download_url=f'https://github.com/raekkeri/django-requestlogs/tarball/{VERSION}',
    packages=find_packages(exclude=['tests']),
    install_requires=requirements,
    extras_require={
        'dev': dev_requirements
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Framework :: Django',
        'Framework :: Django :: 1.11',
        'Framework :: Django :: 2.2',
        'Framework :: Django :: 3.0',
        'Framework :: Django :: 3.1',
        'Framework :: Django :: 3.2',
        'Framework :: Django :: 4.0',
    ],  
)
