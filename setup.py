import sys

from setuptools import setup
from hydroqc2mqtt.__version__ import VERSION

if sys.version_info < (3,7):
    sys.exit('Sorry, Python < 3.7 is not supported')

install_requires = list(val.strip() for val in open('requirements.txt'))
tests_require = list(val.strip() for val in open('test_requirements.txt'))

setup(name='hydroqc2mqtt',
      version=VERSION,
      description=('Daemon managing hydroqc sensors '
                   'through MQTT'),
      author='Hydroqc team',
      url='http://gitlab.com/hydroqc/hydroqc2mqtt',
      package_data={'': ['LICENSE.txt']},
      include_package_data=True,
      packages=['hydroqc2mqtt'],
      entry_points={
          'console_scripts': [
              'hydroqc2mqtt = hydroqc2mqtt.__main__:main'
          ]
      },
      license='MIT',
      install_requires=install_requires,
      tests_require=tests_require,
      classifiers=[
        'Programming Language :: Python :: 3.9',
      ]

)
