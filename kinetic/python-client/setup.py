import os
import setuptools
import kv_client

class CleanCommand(setuptools.Command):
    """Custom clean command to clean up the project."""
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        os.system('rm -vrf *.egg-info')

setuptools.setup(
    name=kv_client.name,
    version=kv_client.version,
    author="Seagate",
    license=open('LICENSE', 'r').read(),
    description="Kinetic Python Client",
    long_description=open('README.md', 'r').read(),
    long_description_content_type="text/markdown",
    url="http://lco-esd-cm01.colo.seagate.com:7990/projects/KT/repos/python-client/browse",
    packages=[kv_client.name],
    install_requires=['protobuf'],
    classifiers=["Programming Language :: Python :: 2.7"],
    python_requires='>=2.7,!=3.*',
    cmdclass={'clean': CleanCommand}
)
