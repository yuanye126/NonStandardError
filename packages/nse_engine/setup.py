from setuptools import setup, find_packages

setup(
    name="nse_engine",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.0",
        "numpy>=1.24",
        "statsmodels>=0.14",
        "linearmodels>=5.3",
        "scipy>=1.10",
        "pyarrow>=12.0",
        "openpyxl>=3.1",
    ],
    python_requires=">=3.11",
)
