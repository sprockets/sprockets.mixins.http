sprockets.mixins.http
=====================
HTTP Client Mixin for Tornado RequestHandlers. Automatically retries on errors, sleep when rate limited, and handles content encoding and decoding using `MsgPack <http://msgpack.org>`_ and JSON.

|Version| |Travis| |CodeCov| |Docs|

Installation
------------
``sprockets.mixins.http`` is available on the
`Python Package Index <https://pypi.python.org/pypi/sprockets.mixins.http>`_
and can be installed via ``pip`` or ``easy_install``:

.. code-block:: bash

   pip install sprockets.mixins.http

If you would like to use `tornado.curl_httpclient.CurlAsyncHTTPClient`,
you can install `pycurl <http://pycurl.io>`_ with:

.. code-block:: bash

   pip install sprockets.mixins.http[curl]

Documentation
-------------
http://pythonhosted.org/sprockets.mixins.http/

Requirements
------------
- `ietfparse <http://ietfparse.readthedocs.io>`_ >=1.4.1,<2
- `tornado <http://www.tornadoweb.org/>`_ >=4.2.0,<5
- `u-msgpack-python <https://pypi.python.org/pypi/u-msgpack-python>`_ >=2.1,<3

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


    if __name__ == "__main__":
       app = web.Application([(r'/', RequestHandler)])
       app.listen(8000)
       ioloop.IOLoop.current().start()


As with Tornado, to use the curl client which has numerous benefits:

.. code:: python

    from tornado import gen, httpclient, ioloop, web
    from sprockets.mixins import http

    httpclient.AsyncHTTPClient.configure(
        'tornado.curl_httpclient.CurlAsyncHTTPClient')


    class RequestHandler(http.HTTPClientMixin, web.RequestHandler):

       @gen.coroutine
       def get(self, *args, **kwargs):
           response = yield self.http_fetch('https://api.github.com')
           if not response.ok:
               self.set_status(response.code)
           self.write(response.body)


    if __name__ == "__main__":
       app = web.Application([(r'/', RequestHandler)])
       app.listen(8000)
       ioloop.IOLoop.current().start()

Environment Variables
---------------------

+------------------+----------------------------------------------------------+
| HTTP_MAX_CLIENTS | An optional setting that specifies the maximum number of |
|                  | simultaneous asynchronous HTTP requests. If not          |
|                  | specified, the default Tornado value of 10 will be used. |
+------------------+----------------------------------------------------------+

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
   :target: http://pythonhosted.org/sprockets.mixins.http/
