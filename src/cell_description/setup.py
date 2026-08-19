from glob import glob

from setuptools import find_packages, setup

package_name = 'cell_description'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Albus',
    maintainer_email='albus@example.com',
    description='Static geometry and calibrated extrinsics for a robot cell.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'extrinsics_publisher = cell_description.extrinsics_publisher:main',
        ],
    },
)
