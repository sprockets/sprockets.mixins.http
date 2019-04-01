Version History
===============

`2.0.1`_ Apr 1, 2019
--------------------
- Fix a bug with the rejected consumer User-Agent behavior

`2.0.0`_ Apr 1, 2019
--------------------
- Refactor the HTTPResponse to a stand-alone class
  - Add ``history`` attribute of the response with all response objects
  - Add ``links`` attribute of the response with the parsed link header if set
  - Add ``exceptions`` attribute with stack of exceptions returned as responses
- Add ``dont_retry`` as argument to ``http_fetch`` method
- Change logging level in a few places to a more appropriate level
- Add support for rejected consumers when auto-creating the ``User-Agent`` header
- Add the netloc of a request to the log entry created when rate limited
- Use RequestHandler.settings instead of RequestHandler.application.settings
  when auto-creating the ``User-Agent`` header for a Tornado request handler
- Add test coverage of the Warning response header behavior

`1.1.1`_ Jan 9, 2019
--------------------
- Fix failure when response lacks Content-Type header

`1.1.0`_ Oct 11, 2018
---------------------
- Add logging of response ``Warning`` headers

`1.0.9`_ Aug 7, 2018
--------------------
- Add support for Python 3.6 and 3.7
- Add support for Tornado < 6

`1.0.8`_ Feb 7, 2018
--------------------
- Add ``max_redirects`` keyword param
- Add ``validate_cert`` keyword param
- Fix log records always using default number of attempts

`1.0.7`_ Oct 19, 2017
---------------------
- Change the hard pin requirement on umsgpack

`1.0.6`_ Aug 16, 2017
---------------------
- Add ``max_http_attempts`` keyword param

`1.0.5`_ Aug 7, 2017
--------------------
- Add support for allow_nonstandard_methods and max_clients

`1.0.4`_ May 12, 2017
---------------------
- Add support for passing the user_agent parameter per request

`1.0.3`_ Apr 28, 2017
---------------------
- Fix the installer

`1.0.2`_ Apr 26, 2017
---------------------
- Documentation Updates

`1.0.1`_ Apr 26, 2017
---------------------
- Default Accept headers include both msgpack and json

`1.0.0`_ Apr 26, 2017
---------------------
- Initial Version

.. _2.0.1: https://github.com/sprockets/sprockets.mixins.http/compare/2.0.0...2.0.1
.. _2.0.0: https://github.com/sprockets/sprockets.mixins.http/compare/1.1.1...2.0.0
.. _1.1.1: https://github.com/sprockets/sprockets.mixins.http/compare/1.1.0...1.1.1
.. _1.1.0: https://github.com/sprockets/sprockets.mixins.http/compare/1.0.9...1.1.0
.. _1.0.9: https://github.com/sprockets/sprockets.mixins.http/compare/1.0.8...1.0.9
.. _1.0.8: https://github.com/sprockets/sprockets.mixins.http/compare/1.0.7...1.0.8
.. _1.0.7: https://github.com/sprockets/sprockets.mixins.http/compare/1.0.6...1.0.7
.. _1.0.6: https://github.com/sprockets/sprockets.mixins.http/compare/1.0.5...1.0.6
.. _1.0.5: https://github.com/sprockets/sprockets.mixins.http/compare/1.0.4...1.0.5
.. _1.0.4: https://github.com/sprockets/sprockets.mixins.http/compare/1.0.3...1.0.4
.. _1.0.3: https://github.com/sprockets/sprockets.mixins.http/compare/1.0.2...1.0.3
.. _1.0.2: https://github.com/sprockets/sprockets.mixins.http/compare/1.0.1...1.0.2
.. _1.0.1: https://github.com/sprockets/sprockets.mixins.http/compare/1.0.0...1.0.1
.. _1.0.0: https://github.com/sprockets/sprockets.mixins.http/compare/2fc5bad...1.0.0
