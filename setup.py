from distutils.core import setup

import ueli.main


setup(
    name='ueli',
    packages=['ueli'],
    description='Ueli the servant helps to build and deploy at flatfox',

    version=ueli.main.VERSION,
    download_url='https://github.com/flatfox-ag/ueli/tarball/{}'.format(ueli.main.VERSION),

    author='flatfox',
    author_email='info@flatfox.ch',
    url='https://github.com/flatfox-ag/ueli',
    keywords=['software', 'build', 'deploy'],
    classifiers=[],
    entry_points={
        'console_scripts': [
            'ueli = ueli.main:main',
        ]
    },
    install_requires=(
        'click>=6.6',
        'pyyaml>=3.12',
    ),
)
