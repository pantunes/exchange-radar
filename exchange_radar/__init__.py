import tomllib

with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)

toml = data["tool"]["poetry"]


__title__ = toml["name"]
__description__ = toml["description"]
__authors__ = toml["authors"]
__license__ = toml["license"]

__version__ = toml["version"]
