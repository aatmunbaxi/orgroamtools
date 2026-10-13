# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os, sys

sys.path.insert(0, os.path.abspath("../../"))
sys.path.insert(0, os.path.abspath("../../"))


project = "orgroamtools"
copyright = "2023, abaxi"
author = "abaxi"
release = "0.0.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]
napoleon_google_docstring = False
# Render "Attributes" sections as fields, so dataclass fields aren't also
# documented a second time by :undoc-members:
napoleon_use_ivar = True
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "networkx": ("https://networkx.org/documentation/stable", None),
}
autodoc_mock_imports = [
    "networkx",
    "orgparse",
    "re",
    "os",
    "sqlite3",
    "copy",
    "typing",
    "dataclasses",
]
autodoc_default_options = {"private-members": False, "members": True}

mock_modules = [
    "networkx",
    "enum",
    "dataclasses",
    "typing",
    "__future__",
    "os",
    "re",
    "warnings",
    "sqlite3",
    "copy",
    "orgparse",
]
# for name in mock_modules:
#     sys.modules[name] = MagicMock()


templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
