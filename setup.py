#!/usr/bin/env python3
"""
Setup script for S3 Large Directory Upload tool
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="s3-large-upload",
    version="1.0.0",
    author="Deepanshu Narang",
    author_email="dn@hyathi.com",
    description="A robust script for uploading large directories to AWS S3",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/deepanshu-ht/s3-upload-script",
    py_modules=["s3_large_upload"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Archiving :: Backup",
        "Topic :: Internet :: File Transfer Protocol (FTP)",
        "Topic :: Utilities",
    ],
    python_requires=">=3.7",
    install_requires=[
        "boto3>=1.26.0",
        "botocore>=1.29.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black>=22.0",
            "flake8>=4.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "s3-large-upload=s3_large_upload:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.json"],
    },
    keywords="aws s3 upload backup multipart resume progress",
) 