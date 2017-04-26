#!/usr/bin/env python
import sphinx_rtd_theme

needs_sphinx = '1.0'
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx']
templates_path = []
source_suffix = '.rst'
master_doc = 'index'
project = 'sprockets.mixins.http'
author = 'AWeber Communications'
copyright = '2017, AWeber Communications'
version = '1.0.0'
release = '1.0'
exclude_patterns = []
pygments_style = 'sphinx'
html_theme = 'sphinx_rtd_theme'
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
intersphinx_mapping = {
    'python': ('https://docs.python.org/', None),
    'tornado': ('http://www.tornadoweb.org/en/stable/', None),
}
