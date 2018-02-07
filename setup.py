#!/usr/bin/env python
import os.path

import setuptools


def read_requirements(name):
    requirements = []
    try:
        with open(os.path.join('requires', name)) as req_file:
            for line in req_file:
                if '#' in line:
                    line = line[:line.index('#')]
                line = line.strip()
                if line.startswith('-r'):
                    requirements.extend(read_requirements(line[2:].strip()))
                elif line and not line.startswith('-'):
                    requirements.append(line)
    except IOError:
        pass
    return requirements


setuptools.setup(
    name='sprockets.mixins.http',
    version='1.0.8',
    description='HTTP Client Mixin for Tornado RequestHandlers',
    long_description=open('README.rst').read(),
    url='https://github.com/sprockets/sprockets.mixins.http',
    author='AWeber Communications, Inc.',
    author_email='api@aweber.com',
    license='BSD',
    classifiers=[
        'Development Status :: 3 - Alpha', 'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License', 'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    packages=setuptools.find_packages(),
    package_data={'': ['LICENSE', 'README.rst', 'requires/installation.txt']},
    include_package_data=True,
    namespace_packages=['sprockets', 'sprockets.mixins'],
    install_requires=read_requirements('installation.txt'),
    extras_require={'curl': ['pycurl']},
    tests_require=read_requirements('testing.txt'),
    zip_safe=True)
