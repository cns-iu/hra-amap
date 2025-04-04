from setuptools import setup, find_packages

setup(
    name="src",
    version="1.0",
    package_dir={'src': 'src'},
    packages = ['src.registration', 'src.utils']
)