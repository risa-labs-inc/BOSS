from setuptools import setup, find_packages

setup(
    name="boss",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "faiss-cpu",
        "asyncio",
    ],
    python_requires=">=3.8",
) 