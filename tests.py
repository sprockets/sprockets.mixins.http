import json
import logging
import os
from unittest import mock
import uuid

import asynctest
from sprockets.mixins import http
from tornado import httpclient, httputil, testing, web
import umsgpack

LOGGER = logging.getLogger(__name__)


def decode(value):
    """Decode bytes to UTF-8 strings as a singe value, list, or dict.

    :param mixed value:
    :rtype: mixed

    """
    if isinstance(value, list):
        return [decode(v) for v in value]
    elif isinstance(value, dict):
        return {decode(k): decode(v) for k, v in value.items()}
    elif isinstance(value, bytes):
        return value.decode('utf-8')
    return value


class TestHandler(web.RequestHandler):
    def prepare(self):
        status_code = self.status_code()
        reason = None
        if status_code in {423, 429, 503}:
            reason = 'Rate Limited'
        if self.get_query_argument('retry_after', None):
            self.set_header('Retry-After',
                            self.get_query_argument('retry_after'))
        if status_code in {423, 429, 502, 503, 504}:
            self.set_status(status_code, reason=reason)
            self.finish()

    def delete(self, *args, **kwargs):
        self.respond()

    def get(self, *args, **kwargs):
        self.respond()

    def head(self, *args, **kwargs):
        status_code = self.status_code() or 204
        self.set_status(status_code)

    def patch(self, *args, **kwargs):
        self.respond()

    def post(self, *args, **kwargs):
        self.respond()

    def put(self, *args, **kwargs):
        self.respond()

    def get_request_body(self):
        content_type = self.request.headers.get('Content-Type')
        if content_type is not None:
            if content_type == 'application/json' \
                    or content_type.endswith('+json'):
                return json.loads(self.request.body.decode('utf-8'))
            elif content_type == 'application/msgpack' \
                    or content_type.endswith('+msgpack'):
                return umsgpack.unpackb(self.request.body)
        if self.request.body_arguments:
            return self.request.body_arguments
        return self.request.body

    def respond(self):
        status_code = self.status_code() or 200
        self.set_status(status_code)
        if status_code >= 400:
            self.send_response({
                'message': self.get_argument('message', 'Error Message Text'),
                'type': self.get_argument('message', 'Error Type Text'),
                'traceback': None
            })
        else:
            body = self.get_request_body()
            if isinstance(body, dict):
                if 'link' in body:
                    self.add_header('Link', body['link'])
                if 'warning' in body:
                    self.add_header('Warning', body['warning'])
                if 'response' in body:
                    return self.send_response(body['response'])
            self.send_response({
                'headers': dict(self.request.headers),
                'path': self.request.path,
                'args': self.request.arguments,
                'body': self.get_request_body()
            })

    def send_response(self, payload):
        if isinstance(payload, (dict, list)):
            accept = self.request.headers.get('Accept')
            if accept == 'application/json' or accept.endswith('+json'):
                self.set_header('Content-Type', accept)
                return self.write(json.dumps(decode(payload)))
            elif accept == 'application/msgpack' \
                    or accept.endswith('+msgpack'):
                self.set_header('Content-Type', accept)
                return self.write(umsgpack.packb(decode(payload)))
        LOGGER.debug('Bypassed serialization')
        content_type = self.get_argument('content_type', None)
        if content_type:
            LOGGER.debug('Setting response content-type: %r', content_type)
            self.set_header('Content-Type', content_type)
        if 'Correlation-Id' in self.request.headers:
            self.set_header('Correlation-Id',
                            self.request.headers['Correlation-ID'])
        return self.write(decode(payload))

    def status_code(self):
        value = self.get_argument('status_code', None)
        return int(value) if value is not None else None


class MixinTestCase(testing.AsyncHTTPTestCase):
    def setUp(self):
        super().setUp()
        self.correlation_id = str(uuid.uuid4())
        self.mixin = self.create_mixin()

    def get_app(self):
        return web.Application([(r'/(.*)', TestHandler)], **{
            'service': 'test',
            'version': '0.1.0'
        })

    def create_mixin(self, add_correlation=True):
        headers = httputil.HTTPHeaders()
        if add_correlation:
            headers['Correlation-ID'] = self.correlation_id
        mixin = http.HTTPClientMixin()
        mixin.application = self._app
        mixin.settings = self._app.settings
        mixin.DEFAULT_RETRY_TIMEOUT = 0.1
        mixin.request = httputil.HTTPServerRequest('GET',
                                                   'http://test:9999/test',
                                                   headers=headers)
        return mixin

    @testing.gen_test
    def test_consumer_user_agent(self):
        class Process:
            def __init__(self):
                self.consumer_name = 'consumer'
                self.consumer_version = '1.1.1'

        class Consumer(http.HTTPClientMixin):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._process = Process()

        consumer = Consumer()
        response = yield consumer.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'))
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'consumer/1.1.1')

    @testing.gen_test
    def test_consumer_user_agent_error(self):
        class Consumer(http.HTTPClientMixin):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._process = True

        consumer = Consumer()
        response = yield consumer.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'))
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'sprockets.mixins.http/{}'.format(http.__version__))

    @testing.gen_test
    def test_default_user_agent(self):
        mixin = http.HTTPClientMixin()
        response = yield mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'))
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'sprockets.mixins.http/{}'.format(http.__version__))

    @testing.gen_test
    def test_default_user_agent_with_partial_config(self):
        del self._app.settings['version']
        response = yield self.mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'))
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.attempts, 1)
        self.assertGreater(response.duration, 0)
        self.assertEqual(response.code, response.raw.code)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'sprockets.mixins.http/{}'.format(http.__version__))

    @testing.gen_test
    def test_socket_errors(self):
        with mock.patch('tornado.httpclient.AsyncHTTPClient.fetch') as fetch:
            fetch.side_effect = OSError
            response = yield self.mixin.http_fetch(self.get_url('/test'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 599)
        self.assertEqual(response.attempts, 3)
        self.assertIsNone(response.body)
        self.assertIsNone(response.headers)
        self.assertIsNone(response.links)
        self.assertIsNone(response.raw)
        for e in response.exceptions:
            self.assertIsInstance(e, OSError)

    @testing.gen_test
    def test_tornado_httpclient_errors(self):
        with mock.patch('tornado.httpclient.AsyncHTTPClient.fetch') as fetch:
            fetch.side_effect = httpclient.HTTPError(599)
            response = yield self.mixin.http_fetch(self.get_url('/test'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 599)
        self.assertEqual(response.attempts, 3)
        self.assertIsNone(response.body)
        self.assertIsNone(response.headers)
        self.assertIsNone(response.links)
        self.assertIsNone(response.raw)
        for e in response.exceptions:
            self.assertIsInstance(e, httpclient.HTTPError)

    @testing.gen_test
    def test_without_correlation_id_behavior(self):
        mixin = self.create_mixin(False)
        response = yield mixin.http_fetch(
            self.get_url('/error?status_code=502'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 502)
        self.assertEqual(response.attempts, 3)

    @testing.gen_test
    def test_get(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'))
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'test/0.1.0')
        self.assertDictEqual(response.body['args'], {
            'foo': ['bar'],
            'status_code': ['200']
        })
        self.assertEqual(response.links, [])

    @testing.gen_test
    def test_post(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body={
                'foo': 'bar',
                'status_code': 200
            },
        )

        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'test/0.1.0')
        self.assertDictEqual(response.body['body'], {
            'foo': 'bar',
            'status_code': 200
        })

    @testing.gen_test
    def test_get_json(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'),
            request_headers={'Accept': 'application/json'})

        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'test/0.1.0')
        self.assertDictEqual(response.body['args'], {
            'foo': ['bar'],
            'status_code': ['200']
        })

    @testing.gen_test
    def test_get_custom_user_agent(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'),
            request_headers={'Accept': 'application/json'},
            user_agent='custom/3.0.0')

        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'custom/3.0.0')
        self.assertDictEqual(response.body['args'], {
            'foo': ['bar'],
            'status_code': ['200']
        })

    @testing.gen_test
    def test_post_html(self):
        expectation = '<html>foo</html>'
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body=expectation,
            request_headers={
                'Accept': 'text/html',
                'Content-Type': 'text/html'
            },
        )
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'test/0.1.0')
        self.assertEqual(response.body['body'], expectation)

    @testing.gen_test
    def test_post_json(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body={
                'foo': 'bar',
                'status_code': 200
            },
            request_headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })

        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'test/0.1.0')
        self.assertDictEqual(response.body['body'], {
            'foo': 'bar',
            'status_code': 200
        })

    @testing.gen_test
    def test_post_custom_user_agent(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body={
                'foo': 'bar',
                'status_code': 200
            },
            request_headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            user_agent='custom/3.0.0')

        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'custom/3.0.0')
        self.assertDictEqual(response.body['body'], {
            'foo': 'bar',
            'status_code': 200
        })

    @testing.gen_test
    def test_post_msgpack(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body={
                'foo': 'bar',
                'status_code': 200
            },
            request_headers={
                'Accept': 'application/msgpack',
                'Content-Type': 'application/msgpack'
            })
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'test/0.1.0')
        self.assertDictEqual(response.body['body'], {
            'foo': 'bar',
            'status_code': 200
        })

    @testing.gen_test
    def test_post_pre_serialized_json(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body=json.dumps({
                'foo': 'bar',
                'status_code': 200
            }),
            request_headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'test/0.1.0')
        self.assertDictEqual(response.body['body'], {
            'foo': 'bar',
            'status_code': 200
        })

    @testing.gen_test
    def test_post_pre_serialized_msgpack(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body=umsgpack.packb({
                'foo': 'bar',
                'status_code': 200
            }),
            request_headers={
                'Accept': 'application/msgpack',
                'Content-Type': 'application/msgpack'
            })
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'test/0.1.0')
        self.assertDictEqual(response.body['body'], {
            'foo': 'bar',
            'status_code': 200
        })
        self.assertEqual([r.code for r in response.history], [200])

    @testing.gen_test
    def test_rate_limiting_behavior_with_retry_after(self):
        with asynctest.mock.patch(
                'sprockets.mixins.http.asyncio') as aio_module:
            aio_module.sleep = asynctest.CoroutineMock()
            for rate_limit_code in {423, 429, 500, 502, 503}:
                response = yield self.mixin.http_fetch(
                    self.get_url(f'/error?status_code={rate_limit_code}'
                                 f'&retry_after=2'))
                self.assertFalse(response.ok)
                self.assertEqual(response.code, rate_limit_code)
                self.assertEqual(response.attempts,
                                 self.mixin.MAX_HTTP_RETRIES)
                self.assertEqual(
                    [r.code for r in response.history],
                    ([rate_limit_code] * self.mixin.MAX_HTTP_RETRIES))
                self.assertEqual(aio_module.sleep.await_count,
                                 self.mixin.MAX_HTTP_RETRIES - 1)
                aio_module.sleep.assert_has_awaits(
                    ([mock.call(2)] * (self.mixin.MAX_HTTP_RETRIES - 1)))
                aio_module.sleep.reset_mock()

    @testing.gen_test
    def test_rate_limiting_behavior_without_retry_after(self):
        max_attempts = 5
        with asynctest.mock.patch(
                'sprockets.mixins.http.asyncio') as aio_module:
            aio_module.sleep = asynctest.CoroutineMock()
            for rate_limit_code in {423, 429, 500, 502, 503}:
                response = yield self.mixin.http_fetch(
                    self.get_url(f'/error?status_code={rate_limit_code}'),
                    max_http_attempts=max_attempts)
                self.assertFalse(response.ok)
                self.assertEqual(response.code, rate_limit_code)
                self.assertEqual(response.attempts, max_attempts)
                self.assertEqual([r.code for r in response.history],
                                 [rate_limit_code] * max_attempts)
                self.assertEqual(aio_module.sleep.await_count,
                                 max_attempts - 1)
                aio_module.sleep.assert_has_awaits([
                    mock.call((2**attempt) * self.mixin.DEFAULT_RETRY_TIMEOUT)
                    for attempt in range(max_attempts - 1)
                ])
                aio_module.sleep.reset_mock()

    @testing.gen_test
    def test_error_response(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/error?status_code=400&message=Test%20Error'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 400)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body, 'Test Error')

    @testing.gen_test
    def test_fancier_error_response(self):
        self.mixin.simplify_error_response = False
        response = yield self.mixin.http_fetch(
            self.get_url('/error?status_code=400&message=Test%20Error'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 400)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body, {
            'message': 'Test Error',
            'type': 'Test Error',
            'traceback': None
        })

    @testing.gen_test
    def test_error_retry(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/error?status_code=502'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 502)
        self.assertEqual(response.attempts, 3)
        self.assertIsNone(response.body)

    @testing.gen_test
    def test_unsupported_content_type(self):
        with self.assertRaises(ValueError):
            yield self.mixin.http_fetch(
                self.get_url('/test'),
                method='POST',
                body=['foo', 'bar'],
                request_headers={'Content-Type': 'text/html'})

    @testing.gen_test
    def test_unsupported_accept(self):
        expectation = '<html>foo</html>'
        response = yield self.mixin.http_fetch(
            self.get_url('/test?content_type=text/html'),
            method='POST',
            body={'response': expectation},
            request_headers={
                'Accept': 'text/html',
                'Content-Type': 'application/json'
            })
        self.assertTrue(response.ok)
        self.assertEqual(response.headers['Content-Type'], 'text/html')
        self.assertEqual(response.body.decode('utf-8'), expectation)

    @testing.gen_test
    def test_allow_nonstardard_methods(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='DELETE',
            body={
                'foo': 'bar',
                'status_code': 200
            },
            allow_nonstandard_methods=True,
        )
        self.assertTrue(response.ok)

    @testing.gen_test
    def test_max_clients_settings_supported(self):
        os.environ['HTTP_MAX_CLIENTS'] = '25'
        response = yield self.mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'))
        self.assertTrue(response.ok)
        del os.environ['HTTP_MAX_CLIENTS']
        client = httpclient.AsyncHTTPClient()
        self.assertEqual(client.max_clients, 25)

    @testing.gen_test
    def test_missing_content_type(self):
        # Craft a response that lacks a Content-Type header.
        body = 'Do not try to deserialize me'
        response = yield self.mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200&content_type=0'),
            'POST',
            body=body,
            content_type='text/plain')
        self.assertTrue(response.ok)
        del response._responses[-1].headers['Content-Type']
        self.assertIsInstance(response.body, bytes)

    @testing.gen_test
    def test_get_link_header(self):
        body = {
            'link': '<http://example.com/TheBook/chapter2>; '
            'rel="previous"; '
            'title="previous chapter"',
            'status_code': 200
        }
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body=body,
            request_headers={
                'Accept': 'application/msgpack',
                'Content-Type': 'application/msgpack'
            })
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'test/0.1.0')
        self.assertDictEqual(response.body['body'], body)

        expectation = {
            'target': 'http://example.com/TheBook/chapter2',
            'rel': 'previous',
            'title': 'previous chapter'
        }
        self.assertDictEqual(response.links[0], expectation)

    @testing.gen_test
    def test_get_warning_header(self):
        body = {
            'warning': '110 anderson/1.3.37 "Response is stale"',
            'status_code': 200
        }
        with mock.patch.object(http.LOGGER, 'warning') as warning:
            response = yield self.mixin.http_fetch(
                self.get_url('/test'),
                method='POST',
                body=body,
                request_headers={
                    'Accept': 'application/msgpack',
                    'Content-Type': 'application/msgpack'
                })
            warning.assert_called_once()

        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body['headers'].get('User-Agent'),
                         'test/0.1.0')
        self.assertDictEqual(response.body['body'], body)

    @testing.gen_test
    def test_correlation_id_attribute(self):
        mixin = http.HTTPClientMixin()
        mixin.correlation_id = str(uuid.uuid4())
        response = yield mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'))
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.headers['Correlation-Id'],
                         mixin.correlation_id)

    @testing.gen_test
    def test_dont_retry(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/error?status_code=429'), dont_retry={429})
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 429)
        self.assertEqual(response.attempts, 1)
        self.assertEqual([r.code for r in response.history], [429])

    @testing.gen_test
    def test_str_url(self):
        class MyURL:
            def __init__(self, url):
                self._url = url

            def __str__(self):
                return self._url

        mixin = http.HTTPClientMixin()
        response = yield mixin.http_fetch(
            MyURL(self.get_url('/test?foo=bar&status_code=200')))
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.attempts, 1)

    @testing.gen_test
    def test_with_obscene_retry_after(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/error?status_code=429&retry_after=86400'),
            max_http_attempts=2,
            request_timeout=0.25,
        )
        self.assertFalse(response.ok)
        self.assertAlmostEqual(response.duration,
                               response.attempts * 0.25,
                               places=0)

    @testing.gen_test
    def test_that_kwargs_are_passed_through(self):
        chunks = []

        def streaming_callback(chunk):
            chunks.append(chunk)

        response = yield self.mixin.http_fetch(
            self.get_url('/test'), streaming_callback=streaming_callback)
        self.assertTrue(response.ok)
        self.assertGreater(len(chunks), 0)

    @testing.gen_test
    def test_that_client_fails_if_raise_error_is_specified(self):
        for value in (True, False, object()):
            with self.assertRaises(RuntimeError, msg=str(value)):
                yield self.mixin.http_fetch(
                    self.get_url('/error?status_code=410'), raise_error=value)

    @testing.gen_test
    def test_that_empty_bodies_are_serialized(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/'),
            method='POST',
            body={},
            request_headers={'Content-Type': 'application/json'})
        self.assertEqual(200, response.code)
        self.assertEqual({}, response.body['body'])

        response = yield self.mixin.http_fetch(
            self.get_url('/'),
            method='POST',
            body=[],
            request_headers={'Content-Type': 'application/json'})
        self.assertEqual(200, response.code)
        self.assertEqual([], response.body['body'])

    @testing.gen_test
    def test_post_msgpack_suffix(self):
        body = {
            'foo': 'bar',
            'status_code': 200
        }
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body=body,
            request_headers={
                'Accept': 'bar/foo+msgpack',
                'Content-Type': 'foo/bar+msgpack'
            })
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Content-Type'],
                         'bar/foo+msgpack')
        self.assertEqual(response.body['body'], body)

    @testing.gen_test
    def test_post_json_suffix(self):
        body = {
            'foo': 'bar',
            'status_code': 200
        }
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body=body,
            request_headers={
                'Accept': 'bar/foo+json',
                'Content-Type': 'foo/bar+json'
            })
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Content-Type'],
                         'bar/foo+json')
        self.assertEqual(response.body['body'], body)
