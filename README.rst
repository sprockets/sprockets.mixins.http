sprockets.mixins.http
=====================
HTTP Client Mixin for Tornado RequestHandlers. Automatically retries on errors, sleep when rate limited, and handles content encoding and decoding using `MsgPack <https://msgpack.org>`_ and JSON.

|Version| |Travis| |CodeCov| |Docs|

Installation
------------
``sprockets.mixins.http`` is available on the
`Python Package Index <https://pypi.python.org/pypi/sprockets.mixins.http>`_
and can be installed via ``pip``:

.. code-block:: bash

   pip install sprockets.mixins.http

If you would like to use `tornado.curl_httpclient.CurlAsyncHTTPClient`,
you can install `pycurl <https://pycurl.io>`_ with:

.. code-block:: bash

   pip install sprockets.mixins.http[curl]

Documentation
-------------
https://sprocketsmixinshttp.readthedocs.io

Requirements
------------
- `ietfparse <https://ietfparse.readthedocs.io>`_ >=1.5.1
- `tornado <https://www.tornadoweb.org/>`_ >=5
- `sprockets.mixins.mediatype[msgpack] <https://sprocketsmixinsmedia-type.readthedocs.io/>`_ >=3

Example
-------

This examples demonstrates the most basic usage of ``sprockets.mixins.http``

.. code:: python

    from tornado import ioloop, web
    from sprockets.mixins import http


    class RequestHandler(http.HTTPClientMixin, web.RequestHandler):

       async def get(self, *args, **kwargs):
           response = await self.http_fetch('https://api.github.com')
           if not response.ok:
               self.set_status(response.code)
           self.write(response.body)


    if __name__ == "__main__":
       app = web.Application([(r'/', RequestHandler)])
       app.listen(8000)
       ioloop.IOLoop.current().start()


As with Tornado, to use the curl client which has numerous benefits:

.. code:: python

    from tornado import httpclient, ioloop, web
    from sprockets.mixins import http

    httpclient.AsyncHTTPClient.configure(
        'tornado.curl_httpclient.CurlAsyncHTTPClient')


    class RequestHandler(http.HTTPClientMixin, web.RequestHandler):

       async def get(self, *args, **kwargs):
           response = await self.http_fetch('https://api.github.com')
           if not response.ok:
               self.set_status(response.code)
           self.write(response.body)


    if __name__ == "__main__":
       app = web.Application([(r'/', RequestHandler)])
       app.listen(8000)
       ioloop.IOLoop.current().start()

Error Response Body
-------------------

For errors, i.e. a response with HTTP status code in the 400 range...

The HTTPResponse object's body is reduced down to just the error message.
That is this mixin's default behavior.

For a JSON response body with Problem Details (RFC 7807), you may want more
than just the error message.  To gain access to the complete, deserialized
response body; a class that uses this mixin can set:

.. code:: python

   self.simplify_error_response = False


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
   :target: https://badge.fury.io/py/sprockets.mixins.http

.. |Travis| image:: https://travis-ci.org/sprockets/sprockets.mixins.http.svg?branch=master
   :target: https://travis-ci.org/sprockets/sprockets.mixins.http

.. |CodeCov| image:: https://codecov.io/github/sprockets/sprockets.mixins.http/coverage.svg?branch=master
   :target: https://codecov.io/github/sprockets/sprockets.mixins.http?branch=master

.. |Docs| image:: https://img.shields.io/readthedocs/sprocketsmixinshttp
   :target: https://sprocketsmixinshttp.readthedocs.io/
