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

.. code:: python

    from tornado import gen, ioloop, web
    from sprockets.mixins import http


    class RequestHandler(http.HTTPClientMixin, web.RequestHandler):

       @gen.coroutine
       def get(self, *args, **kwargs):
           response = yield self.http_fetch('https://api.github.com')
           if not response.ok:
               self.set_status(response.code)
           self.write(response.body)
           self.finish()


    if __name__ == "__main__":
       app = web.Application([web.url(r'/', RequestHandler)])
       app.listen(8000)
       ioloop.IOLoop.current().start()


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
