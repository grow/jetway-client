"""WebReview Client Setup."""

import os
import re
from setuptools import find_packages
from setuptools import setup


DEP_RE = re.compile(r'([\S]*)\s?=\s? [\"\']?([^\'\"]*)[\"\']?', re.IGNORECASE)
INSTALL_REQ = []

with open('Pipfile') as pipfile:
    in_dep_section = False
    for line in pipfile.readlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if in_dep_section:
            if line.startswith('['):
                in_dep_section = False
                continue

            line_match = DEP_RE.match(line)
            if line_match:
                INSTALL_REQ.append(
                    '{}{}'.format(line_match.group(1).strip('"'), line_match.group(2)))
        elif line == '[packages]':
            in_dep_section = True

setup(
    name='webreview',
    version=open(os.path.join('webreview', 'VERSION')).read().strip(),
    description=(
        'Client library for the WebReview static site staging service.'
    ),
    url='https://github.com/grow/webreview-client',
    license='MIT',
    author='Grow SDK Authors',
    author_email='code@grow.io',
    include_package_data=True,
    install_requires=INSTALL_REQ,
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
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ])
