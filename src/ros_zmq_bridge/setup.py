from glob import glob

from setuptools import find_packages, setup

package_name = 'ros_zmq_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Albus',
    maintainer_email='albus@example.com',
    description='ROS <-> ZMQ frame packet bridge.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'bridge_node = ros_zmq_bridge.bridge_node:main',
        ],
    },
)
