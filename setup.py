import versioneer
from setuptools import setup, find_packages
from os import path, environ

cur_dir = path.abspath(path.dirname(__file__))

with open(path.join(cur_dir, 'requirements.txt'), 'r') as f:
    requirements = f.read().split()


# set up additional dev requirements
with open(path.join(cur_dir, "dev-requirements.txt"), "r") as f:
    dev_requirements = f.read().split()


setup(
    name='lume-impact',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    packages=find_packages(),  
    package_dir={'xopt':'xopt'},
    url='https://github.com/ChristopherMayes/lume-impact',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    install_requires=requirements,
    extras_require= {
        "dev": dev_requirements,
    },
    include_package_data=True,
    python_requires='>=3.6'
)
