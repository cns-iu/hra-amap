from setuptools import setup, find_packages

setup(
    name="hra_amap",
    version="1.0",
    package_dir={"hra_amap": "hra_amap"},
    packages=["hra_amap.registration", "hra_amap.utils"],
)
