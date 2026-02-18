from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("intellibox")
except PackageNotFoundError:
    __version__ = "dev"
