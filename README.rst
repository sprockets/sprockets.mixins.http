sprockets.mixins.http
=====================
HTTP Client Mixin for Tornado RequestHandlers.

|Version| |Travis| |CodeCov| |Docs|

Installation
------------
``sprockets.mixins.http`` is available on the
`Python Package Index <https://pypi.python.org/pypi/sprockets.mixins.http>`_
and can be installed via ``pip`` or ``easy_install``:

.. code-block:: bash

   pip install sprockets.mixins.http

Documentation
-------------
https://pythonhosted.org/sprockets.mixins.http

Requirements
------------
- pycurl
- tornado>=4.2.0,<5

Example
-------

This examples demonstrates the most basic usage of ``sprockets.mixins.http``

.. code:: bash

   python my-example-app.py


.. code:: python

   from tornado import gen, web
   from sprockets.mixins import amqp

   def make_app(**settings):
       return web.Application(
           [
               web.url(r'/', RequestHandler),
           ], **settings)


   class RequestHandler(http.HTTPClientMixin,
                        correlation.HandlerMixin,
                        web.RequestHandler):

       @gen.coroutine
       def get(self, *args, **kwargs):
           response = yield self.http_fetch('https://www.google.com')

License
-------
``sprockets.mixins.http`` is released under the `3-Clause BSD license <https://github.com/sprockets/sprockets.mixins.http/blob/master/LICENSE>`_.

.. |Version| image:: https://badge.fury.io/py/sprockets.mixins.http.svg?
   :target: http://badge.fury.io/py/sprockets.mixins.http

.. |Travis| image:: https://travis-ci.org/sprockets/sprockets.mixins.http.svg?branch=master
   :target: https://travis-ci.org/sprockets/sprockets.mixins.http

.. |CodeCov| image:: http://codecov.io/github/sprockets/sprockets.mixins.http/coverage.svg?branch=master
   :target: https://codecov.io/github/sprockets/sprockets.mixins.http?branch=master

.. |Docs| image:: https://img.shields.io/badge/docs-pythonhosted-green.svg
   :target: https://pythonhosted.com/sprockets.mixins.http
