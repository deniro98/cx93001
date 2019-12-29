import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cx93001",
    version="0.0.3",
    author="havocsec",
    author_email="havocsec-os@pm.me",
    description="Python 3 interface for Conexant CX93001 chipset based voice modems.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/havocsec/cx93001",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: Unix",
    ],
    install_requires=[
        "pyserial",
        "pydub"
    ],
    python_requires=">=3",
)
