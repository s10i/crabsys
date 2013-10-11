from distutils.core import setup

setup(
    name='CRABSys',
    version='0.1.0',
    author='Felipe Menezes Machado',
    author_email='felipe@s10i.com.br',
    packages=['crabsys'],
    scripts=['bin/crab'],
    package_data={'crabsys': ['resources/templates/*', 'resources/*.cmake']},
    url='http://pypi.python.org/pypi/CRABSys/',
    license='LICENSE.txt',
    description='C/C++ Recursive Automated Build System',
    long_description=open('README.md').read(),
    install_requires=[
    ],
)
