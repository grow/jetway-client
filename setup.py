import uuid
import os
from setuptools import find_packages
from setuptools import setup
from pip import req

_here = os.path.dirname(__file__)
_install_requirements = req.parse_requirements(
    'requirements.txt', session=uuid.uuid1())


setup(
    name='webreview',
    version=open(os.path.join(_here, 'webreview', 'VERSION')).read().strip(),
    description=(
        'Client library for the WebReview static site staging service.'
    ),
    url='https://github.com/grow/webreview-client',
    license='MIT',
    author='Grow SDK Authors',
    author_email='hello@grow.io',
    include_package_data=True,
    install_requires=[str(ir.req) for ir in _install_requirements],
    packages=find_packages(),
    keywords=[
        'grow',
        'cms',
        'static site generator',
        's3',
        'google cloud storage',
        'content management'
    ],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ])
