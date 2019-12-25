#!/usr/bin/env python3

from setuptools import setup


setup(
    name='fuo_xiami',
    version='0.2.1',
    description='feeluown xiami plugin',
    author='Cosven',
    author_email='yinshaowen241@gmail.com',
    packages=[
        'fuo_xiami',
    ],
    package_data={
        '': []
        },
    url='https://github.com/feeluown/feeluown-xiami',
    keywords=['feeluown', 'plugin', 'xiami'],
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3 :: Only',
        ),
    install_requires=[
        'feeluown>=3.2.dev0',
        'marshmallow>=3.0',
        'requests',
    ],
    entry_points={
        'fuo.plugins_v1': [
            'xiami = fuo_xiami',
        ]
    },
)
