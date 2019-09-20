"""
HTTP Client Mixin
=================
A Tornado Request Handler Mixin that provides functions for making HTTP
requests.

"""
import asyncio
import logging
import os
import time
from urllib import parse

from ietfparse import algorithms, errors, headers
from sprockets.mixins.mediatype import transcoders
from tornado import httpclient

__version__ = '2.2.1'

LOGGER = logging.getLogger(__name__)

CONTENT_TYPE_JSON = headers.parse_content_type('application/json')
CONTENT_TYPE_MSGPACK = headers.parse_content_type('application/msgpack')
AVAILABLE_CONTENT_TYPES = [CONTENT_TYPE_JSON, CONTENT_TYPE_MSGPACK]
DEFAULT_USER_AGENT = 'sprockets.mixins.http/{}'.format(__version__)


class HTTPResponse:
    """Encapsulate the response(s) for requests made using the
     :meth:`~sprockets.mixins.http.HTTPClientMixin.http_fetch` method.

    """

    def __init__(self):
        self._exceptions = []
        self._finish = None
        self._json = transcoders.JSONTranscoder()
        self._msgpack = transcoders.MsgPackTranscoder()
        self._responses = []
        self._start = time.time()

    def __len__(self):
        """Return the length of the exception stack and response stack.

        :rtype: int

        """
        return len(self._exceptions) + len(self._responses)

    def append_exception(self, error):
        """Append an exception raised when making a request

        :param Exception error: The exception raised when making the request

        """
        self._exceptions.append(error)

    def append_response(self, response):
        """Append the response to the stack of responses.

        :param tornado.httpclient.HTTPResponse response: The HTTP response

        """
        self._responses.append(response)
        if 'Warning' in response.headers:
            LOGGER.warning(
                'HTTP %s %s Warning (%s): %s (attempt %s)',
                response.request.method, response.request.url,
                response.code, response.headers['Warning'],
                len(self._responses))

    def finish(self):
        """Mark the processing as finished"""
        self._finish = time.time()

    @property
    def attempts(self):
        """Return the number of HTTP attempts made by calculating the number
        of exceptions and responses the object contains.

        :rtype: int

        """
        return len(self)

    @property
    def body(self):
        """Returns the HTTP response body, deserialized if possible.

        :rtype: mixed

        """
        if not self._responses:
            return None
        if self._responses[-1].code >= 400:
            return self._error_message()
        return self._deserialize()

    @property
    def code(self):
        """Returns the HTTP status code of the response.

        :rtype: int

        """
        return self._responses[-1].code if self._responses else 599

    @property
    def duration(self):
        """Return the calculated duration for the total amount of time
        across all retries.

        :rtype: float

        """
        return (self._finish or time.time()) - self._start

    @property
    def exceptions(self):
        """Return the list of exceptions raised when making the request.

        :rtype: list(Exception)

        """
        return self._exceptions

    @property
    def headers(self):
        """Return the HTTP Response headers as a dict.

        :rtype: dict

        """
        if not self._responses:
            return None
        return dict(self._responses[-1].headers)

    @property
    def history(self):
        """Return all of the HTTP responses for the request.

        :rtype: list(tornado.httpclient.HTTPResponse)

        """
        return self._responses

    @property
    def links(self):
        """Return the parsed link header if it was set, returning a list of
        the links as a dict.

        :rtype: list(dict()) or None

        """
        if not self._responses:
            return None
        if 'Link' in self._responses[-1].headers:
            links = []
            for l in headers.parse_link(self._responses[-1].headers['Link']):
                link = {'target': l.target}
                link.update({k: v for (k, v) in l.parameters})
                links.append(link)
            return links

    @property
    def ok(self):
        """Returns `True` if the response status code was between 200 and 399.
        Returns `False` if no responses were received or the response status
        code was >= 400.

        :rtype bool

        """
        if not self._responses:
            return False
        return 200 <= self._responses[-1].code < 400

    @property
    def raw(self):
        """Return the raw tornado HTTP Response object

        :rtype: tornado.httpclient.HTTPResponse

        """
        if not self._responses:
            return None
        return self._responses[-1]

    def _decode(self, value):
        """Decode bytes to UTF-8 strings as a singe value, list, or dict.

        :param mixed value: The value to decode
        :rtype: mixed

        """
        if isinstance(value, list):
            return [self._decode(v) for v in value]
        elif isinstance(value, dict):
            return {self._decode(k): self._decode(v)
                    for k, v in value.items()}
        elif isinstance(value, bytes):
            return value.decode('utf-8')
        return value

    def _deserialize(self):
        """Try and deserialize a response body based upon the specified
        content type.

        :rtype: mixed

        """
        if not self._responses or not self._responses[-1].body:
            return None
        if 'Content-Type' not in self._responses[-1].headers:
            return self._responses[-1].body
        try:
            content_type = algorithms.select_content_type(
                [headers.parse_content_type(
                    self._responses[-1].headers['Content-Type'])],
                AVAILABLE_CONTENT_TYPES)
        except errors.NoMatch:
            return self._responses[-1].body

        if content_type[0] == CONTENT_TYPE_JSON:
            return self._decode(
                self._json.loads(self._decode(self._responses[-1].body)))
        elif content_type[0] == CONTENT_TYPE_MSGPACK:  # pragma: nocover
            return self._decode(
                self._msgpack.unpackb(self._responses[-1].body))

    def _error_message(self):
        """Try and extract the error message from a HTTP error response.

        :rtype: str

        """
        body = self._deserialize()
        return body.get('message', body) if isinstance(body, dict) else body


class HTTPClientMixin:
    """Mixin for making http requests using the asynchronous
    :py:meth:`~sprockets.mixins.http.HTTPClientMixin.http_fetch` method.

    """

    DEFAULT_CONNECT_TIMEOUT = 10
    DEFAULT_REQUEST_TIMEOUT = 60

    MAX_HTTP_RETRIES = 3
    MAX_REDIRECTS = 5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__hcm_json = transcoders.JSONTranscoder()
        self.__hcm_msgpack = transcoders.MsgPackTranscoder()

    async def http_fetch(self, url,
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
                         allow_nonstandard_methods=False,
                         dont_retry=None):
        """Perform a HTTP request

        Will retry up to ``self.MAX_HTTP_RETRIES`` times.

        :param str url: The URL for the request
        :param str method: The HTTP request method, defaults to ``GET``
        :param dict request_headers: Headers to include in the HTTP request
        :param mixed body: The HTTP request body to send with the request
        :param content_type: The mime type to use for requests & responses.
            Defaults to ``application/msgpack``
        :type content_type: :py:class:`~ietfparse.datastructures.ContentType`
            or str
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
            certificate? Default is True
        :param bool allow_nonstandard_methods: Allow methods that don't adhere
            to the HTTP spec.
        :param set dont_retry: A list of status codes that will not be retried
            if an error is returned. Default: set({})
        :rtype: HTTPResponse

        """
        response = HTTPResponse()

        request_headers = self._http_req_apply_default_headers(
            request_headers, content_type, body)

        if body:
            body = self._http_req_body_serialize(
                body, request_headers['Content-Type'])

        if not dont_retry:
            dont_retry = set({})

        client = httpclient.AsyncHTTPClient()

        # Workaround for Tornado defect.
        if hasattr(client, 'max_clients') and os.getenv('HTTP_MAX_CLIENTS'):
            client.max_clients = int(os.getenv('HTTP_MAX_CLIENTS'))

        for attempt in range(0, max_http_attempts):
            LOGGER.debug('%s %s (Attempt %i of %i) %r',
                         method, url, attempt + 1, max_http_attempts,
                         request_headers)
            if attempt > 0:
                request_headers['X-Retry-Attempt'] = str(attempt + 1)
            try:
                resp = await client.fetch(
                    str(url),
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
            except (OSError, httpclient.HTTPError) as error:
                response.append_exception(error)
                LOGGER.warning(
                    'HTTP Request Error for %s to %s attempt %i of %i: %s',
                    method, url, attempt + 1, max_http_attempts, error)
                continue

            # Keep track of each response
            response.append_response(resp)

            # If the response is ok, finish and exit
            if response.ok:
                response.finish()
                return response
            elif resp.code in dont_retry:
                break
            elif resp.code in {423, 429}:
                await self._http_resp_rate_limited(resp)
            elif resp.code < 500:
                LOGGER.debug('HTTP Response Error for %s to %s'
                             'attempt %i of %i (%s): %s',
                             method, url, resp.code, attempt + 1,
                             max_http_attempts, response.body)
                response.finish()
                return response

            LOGGER.warning(
                'HTTP Error for %s to %s, attempt %i of %i (%s): %s',
                method, url, attempt + 1, max_http_attempts, resp.code,
                response.body)

        LOGGER.warning('HTTP %s to %s failed after %i attempts', method, url,
                       max_http_attempts)
        response.finish()
        return response

    def _http_req_apply_default_headers(self, request_headers,
                                        content_type, body):
        """Set default values for common HTTP request headers

        :param dict request_headers: The HTTP request headers
        :param content_type: The mime-type used in the request/response
        :type content_type: :py:class:`ietfparse.datastructures.ContentType`
            or str
        :param mixed body: The request body
        :rtype: dict

        """
        if not request_headers:
            request_headers = {}
        request_headers.setdefault(
            'Accept', ', '.join([str(ct) for ct in AVAILABLE_CONTENT_TYPES]))
        if body:
            request_headers.setdefault(
                'Content-Type', str(content_type) or str(CONTENT_TYPE_MSGPACK))
        if hasattr(self, 'correlation_id'):
            request_headers.setdefault(
                'Correlation-Id', self.correlation_id)
        elif hasattr(self, 'request') and \
                self.request.headers.get('Correlation-Id'):
            request_headers.setdefault(
                'Correlation-Id', self.request.headers['Correlation-Id'])
        return request_headers

    def _http_req_body_serialize(self, body, content_type):
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
            return self.__hcm_json.dumps(body)
        elif content_type == CONTENT_TYPE_MSGPACK:
            return self.__hcm_msgpack.packb(body)
        raise ValueError('Unsupported Content Type')

    def _http_req_user_agent(self):
        """Return the User-Agent value to specify in HTTP requests, defaulting
        to ``service/version`` if configured in the application settings,
        or if used in a consumer, it will attempt to obtain a user-agent from
        the consumer's process. If it can not auto-set the User-Agent, it
        defaults to ``sprockets.mixins.http/[VERSION]``.

        :rtype: str

        """
        # Tornado Request Handler
        try:
            return '{}/{}'.format(
                self.settings['service'], self.settings['version'])
        except (AttributeError, KeyError):
            pass

        # Rejected Consumer
        if hasattr(self, '_process'):
            try:
                return '{}/{}'.format(
                    self._process.consumer_name,
                    self._process.consumer_version)
            except AttributeError:
                pass
        return DEFAULT_USER_AGENT

    @staticmethod
    def _http_resp_rate_limited(response):
        """Extract the ``Retry-After`` header value if the request was rate
        limited and return a future to sleep for the specified duration.

        :param tornado.httpclient.HTTPResponse response: The response
        :rtype: tornado.concurrent.Future

        """
        parsed = parse.urlparse(response.request.url)
        duration = int(response.headers.get('Retry-After', 3))
        LOGGER.warning('Rate Limited by %s, retrying in %i seconds',
                       parsed.netloc, duration)
        return asyncio.sleep(duration)
