# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os, sys
print(sys.path)
sys.path.insert(0, os.path.abspath('../'))

project = 'orgroamtools'
copyright = '2023, abaxi'
author = 'abaxi'
release = '0.0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc',
              'sphinx.ext.napoleon',
              'sphinx.ext.doctest',
              'sphinx.ext.autosummary',
              'sphinx.ext.githubpages',
              'sphinx_autodoc_typehints']

autodoc_default_options = {
    "members" : True,
    "undoc-memebers": True,
    "private-member" : True
}
napoleon_numpy_docstring = True
templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_output_dir = "build/html"
# html_static_path = ['build/html/_static']
