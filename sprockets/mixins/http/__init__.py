"""
HTTP Client Mixin
=================
A Tornado Request Handler Mixin that provides functions for making HTTP
requests.

"""
import collections
import json
import logging
import os
import socket
import time

from ietfparse import algorithms, errors, headers
from tornado import gen, httpclient
import umsgpack

__version__ = '1.0.8'

LOGGER = logging.getLogger(__name__)

CONTENT_TYPE_JSON = headers.parse_content_type('application/json')
CONTENT_TYPE_MSGPACK = headers.parse_content_type('application/msgpack')
DEFAULT_USER_AGENT = 'sprockets.mixins.http/{}'.format(__version__)


HTTPResponse = collections.namedtuple(
    'HTTPResponse',
    ['ok', 'code', 'headers', 'body', 'raw', 'attempts', 'duration'])
"""Response in the form of a :class:`~collections.namedtuple` returned from
:meth:`~sprockets.mixins.http.HTTPClientMixin.http_fetch` that provides a
slightly higher level of functionality than Tornado's
:class:`tornado.httpclient.HTTPResponse` class.

:param bool ok: The response status code was between 200 and 308
:param int code: The HTTP response status code
:param dict headers: The HTTP response headers
:param mixed body: The deserialized HTTP response body if available/supported
:param tornado.httpclient.HTTPResponse raw: The original Tornado HTTP
    response object for the request
:param int attempts: The number of HTTP request attempts made
:param float duration: The total duration of time spent making the request(s)

"""


class HTTPClientMixin(object):
    """Mixin for making http requests. Requests using the asynchronous
    :meth:`HTTPClientMixin.http_fetch` method """

    AVAILABLE_CONTENT_TYPES = [CONTENT_TYPE_JSON, CONTENT_TYPE_MSGPACK]

    DEFAULT_CONNECT_TIMEOUT = 10
    DEFAULT_REQUEST_TIMEOUT = 60

    MAX_HTTP_RETRIES = 3
    MAX_REDIRECTS = 5

    @gen.coroutine
    def http_fetch(self, url,
                   method='GET',
                   request_headers=None,
                   body=None,
                   content_type=CONTENT_TYPE_MSGPACK,
                   follow_redirects=False,
                   max_redirects=MAX_REDIRECTS,
                   connect_timeout=DEFAULT_CONNECT_TIMEOUT,
                   request_timeout=DEFAULT_REQUEST_TIMEOUT,
                   max_http_attempts=MAX_HTTP_RETRIES,
                   auth_username=None,
                   auth_password=None,
                   user_agent=None,
                   validate_cert=True,
                   allow_nonstandard_methods=False):
        """Perform a HTTP request

        Will retry up to ``self.MAX_HTTP_RETRIES`` times.

        :param str url: The URL for the request
        :param str method: The HTTP request method, defaults to ``GET``
        :param dict request_headers: Headers to include in the HTTP request
        :param mixed body: The HTTP request body to send with the request
        :param content_type: The mime type to use for requests & responses.
            Defaults to ``application/msgpack``
        :type content_type: :class:`~ietfparse.datastructures.ContentType` or
            str
        :param bool follow_redirects: Follow HTTP redirects when received
        :param int max_redirects: Maximum number of redirects to follow,
            default is 5
        :param float connect_timeout: Timeout for initial connection in
            seconds, default 20 seconds
        :param float request_timeout:  Timeout for entire request in seconds,
            default 20 seconds
        :param int max_http_attempts: Maximum number of times to retry
            a request, default is 3 attempts
        :param str auth_username: Username for HTTP authentication
        :param str auth_password: Password for HTTP authentication
        :param str user_agent: The str used for the ``User-Agent`` header,
            default used if unspecified.
        :param bool validate_cert: For HTTPS requests, validate the server's
            certifacte? Default is True
        :param bool allow_nonstandard_methods: Allow methods that don't adhere
            to the HTTP spec.
        :rtype: HTTPResponse

        """
        request_headers = self._http_req_apply_default_headers(
            request_headers, content_type, body)
        if body:
            body = self._http_req_body_serialize(
                body, request_headers['Content-Type'])

        client = httpclient.AsyncHTTPClient()

        # Workaround for Tornado defect.
        if hasattr(client, 'max_clients') and os.getenv('HTTP_MAX_CLIENTS'):
            client.max_clients = int(os.getenv('HTTP_MAX_CLIENTS'))

        response, start_time = None, time.time()
        for attempt in range(0, max_http_attempts):
            LOGGER.debug('%s %s (Attempt %i of %i) %r',
                         method, url, attempt + 1, max_http_attempts,
                         request_headers)
            try:
                response = yield client.fetch(
                    url,
                    method=method,
                    headers=request_headers,
                    body=body,
                    auth_username=auth_username,
                    auth_password=auth_password,
                    connect_timeout=connect_timeout,
                    request_timeout=request_timeout,
                    user_agent=user_agent or self._http_req_user_agent(),
                    follow_redirects=follow_redirects,
                    max_redirects=max_redirects,
                    raise_error=False,
                    validate_cert=validate_cert,
                    allow_nonstandard_methods=allow_nonstandard_methods)
            except (OSError, socket.gaierror) as error:
                LOGGER.debug('HTTP Request Error for %s to %s'
                             'attempt %i of %i: %s',
                             method, url, attempt + 1,
                             max_http_attempts, error)
                continue
            if 200 <= response.code < 400:
                raise gen.Return(
                    HTTPResponse(
                        True, response.code, dict(response.headers),
                        self._http_resp_deserialize(response),
                        response, attempt + 1, time.time() - start_time))
            elif response.code in {423, 429}:
                yield self._http_resp_rate_limited(response)
            elif 400 <= response.code < 500:
                error = self._http_resp_error_message(response)
                LOGGER.debug('HTTP Response Error for %s to %s'
                             'attempt %i of %i (%s): %s',
                             method, url, response.code, attempt + 1,
                             max_http_attempts, error)
                raise gen.Return(
                    HTTPResponse(
                        False, response.code, dict(response.headers),
                        error, response, attempt + 1,
                        time.time() - start_time))
            elif response.code >= 500:
                LOGGER.error('HTTP Response Error for %s to %s, '
                             'attempt %i of %i (%s): %s',
                             method, url, attempt + 1, max_http_attempts,
                             response.code,
                             self._http_resp_error_message(response))

        LOGGER.warning('HTTP Get %s failed after %i attempts', url,
                       max_http_attempts)
        if response:
            raise gen.Return(
                HTTPResponse(
                    False, response.code, dict(response.headers),
                    self._http_resp_error_message(response) or response.body,
                    response, max_http_attempts,
                    time.time() - start_time))
        raise gen.Return(
            HTTPResponse(
                False, 599, None, None, None, max_http_attempts,
                time.time() - start_time))

    def _http_req_apply_default_headers(self, request_headers,
                                        content_type, body):
        """Set default values for common HTTP request headers

        :param dict request_headers: The HTTP request headers
        :param content_type: The mime-type used in the request/response
        :type content_type: :class:`ietfparse.datastructures.ContentType`
            or str
        :param mixed body: The request body
        :rtype: dict

        """
        if not request_headers:
            request_headers = {}
        request_headers.setdefault(
            'Accept', ', '.join([str(ctype) for ctype in
                                 self.AVAILABLE_CONTENT_TYPES]))
        if body:
            request_headers.setdefault(
                'Content-Type', str(content_type) or str(CONTENT_TYPE_MSGPACK))
        if hasattr(self, 'request'):
            if self.request.headers.get('Correlation-Id'):
                request_headers.setdefault(
                    'Correlation-Id', self.request.headers['Correlation-Id'])
        return request_headers

    @staticmethod
    def _http_req_body_serialize(body, content_type):
        """Conditionally serialize the request body value if mime_type is set
        and it's serializable.

        :param mixed body: The request body
        :param str content_type: The content type for the request body
        :raises: ValueError

        """
        if not body or not isinstance(body, (dict, list)):
            return body

        content_type = headers.parse_content_type(content_type)
        if content_type == CONTENT_TYPE_JSON:
            return json.dumps(body)
        elif content_type == CONTENT_TYPE_MSGPACK:
            return umsgpack.packb(body)
        raise ValueError('Unsupported Content Type')

    def _http_req_user_agent(self):
        """Return the User-Agent value to specify in HTTP requests, defaulting
        to ``service/version`` if configured in the application settings,
        otherwise defaulting to ``sprockets.mixins.http/[VERSION]``.

        :rtype: str

        """
        if hasattr(self, 'application'):
            if self.application.settings.get('service') and \
                    self.application.settings.get('version'):
                return '{}/{}'.format(
                    self.application.settings['service'],
                    self.application.settings['version'])
        return DEFAULT_USER_AGENT

    def _http_resp_decode(self, value):
        """Decode bytes to UTF-8 strings as a singe value, list, or dict.

        :param mixed value:
        :rtype: mixed
        """
        if isinstance(value, list):
            return [self._http_resp_decode(v) for v in value]
        elif isinstance(value, dict):
            return dict([(self._http_resp_decode(k),
                          self._http_resp_decode(v))
                         for k, v in value.items()])
        elif isinstance(value, bytes):
            return value.decode('utf-8')
        return value

    def _http_resp_deserialize(self, response):
        """Try and deserialize a response body based upon the specified
        content type.

        :param tornado.httpclient.HTTPResponse: The HTTP response to decode
        :rtype: mixed

        """
        if not response.body:
            return None
        try:
            content_type = algorithms.select_content_type(
                [headers.parse_content_type(response.headers['Content-Type'])],
                self.AVAILABLE_CONTENT_TYPES)
        except errors.NoMatch:
            return response.body

        if content_type[0] == CONTENT_TYPE_JSON:
            return self._http_resp_decode(
                json.loads(self._http_resp_decode(response.body)))
        elif content_type[0] == CONTENT_TYPE_MSGPACK:
            return self._http_resp_decode(umsgpack.unpackb(response.body))

    def _http_resp_error_message(self, response):
        """Try and extract the error message from a HTTP error response.

        :param tornado.httpclient.HTTPResponse response: The response
        :rtype: str

        """
        response_body = self._http_resp_deserialize(response)
        if isinstance(response_body, dict) and 'message' in response_body:
            return response_body['message']
        return response_body

    @staticmethod
    def _http_resp_rate_limited(response):
        """Extract the ``Retry-After`` header value if the request was rate
        limited and return a future to sleep for the specified duration.

        :param tornado.httpclient.HTTPResponse response: The response
        :rtype: tornado.concurrent.Future

        """
        duration = int(response.headers.get('Retry-After', 3))
        LOGGER.warning('Rate Limited by, retrying in %i seconds', duration)
        return gen.sleep(duration)
