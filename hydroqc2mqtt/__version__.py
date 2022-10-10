"""Hydroqc2mqtt version."""
from importlib.metadata import PackageNotFoundError, version

try:
    VERSION = version("hydroqc2mqtt")
except PackageNotFoundError:
    # package is not installed
    print("Python package `hydroqc2mqtt` is not installed. Install it using pip")
