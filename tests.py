import json
import logging
import uuid

from tornado import httputil, testing, web
import mock
import umsgpack

from sprockets.mixins import http

LOGGER = logging.getLogger(__name__)


def decode(value):
    """Decode bytes to UTF-8 strings as a singe value, list, or dict.

    :param mixed value:
    :rtype: mixed

    """
    if isinstance(value, list):
        return [decode(v) for v in value]
    elif isinstance(value, dict):
        return dict([(decode(k), decode(v)) for k, v in value.items()])
    elif isinstance(value, bytes):
        return value.decode('utf-8')
    return value


class TestHandler(web.RequestHandler):

    def prepare(self):
        status_code = self.status_code()
        if status_code == 429:
            self.add_header('Retry-After', '1')
            self.set_status(429)
            self.finish()
        elif status_code in {502, 504}:
            self.set_status(status_code)
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
        if 'Content-Type' in self.request.headers:
            if self.request.headers['Content-Type'] == 'application/json':
                return json.loads(self.request.body.decode('utf-8'))
            elif self.request.headers['Content-Type'] == 'application/msgpack':
                return umsgpack.unpackb(self.request.body)
        if self.request.body_arguments:
            return self.request.body_arguments
        return self.request.body

    def respond(self):
        status_code = self.status_code() or 200
        self.set_status(status_code)
        if status_code >= 400:
            self.send_response({
                'message': self.get_argument('message',
                                             'Error Message Text'),
                'type': self.get_argument('message', 'Error Type Text'),
                'traceback': None})
        else:
            body = self.get_request_body()
            if isinstance(body, dict) and 'response' in body:
                return self.send_response(body['response'])
            self.send_response({'headers': dict(self.request.headers),
                                'path': self.request.path,
                                'args': self.request.arguments,
                                'body': self.get_request_body()})

    def send_response(self, payload):
        if isinstance(payload, (dict, list)):
            if self.request.headers.get('Accept') == 'application/json':
                self.set_header('Content-Type', 'application/json')
                return self.write(decode(payload))
            elif self.request.headers.get('Accept') == 'application/msgpack':
                self.set_header('Content-Type', 'application/msgpack')
                return self.write(umsgpack.packb(decode(payload)))
        LOGGER.debug('Bypassed serialization')
        content_type = self.get_argument('content_type', None)
        if content_type:
            LOGGER.debug('Setting response content-type: %r', content_type)
            self.set_header('Content-Type', content_type)
        return self.write(decode(payload))

    def status_code(self):
        value = self.get_argument('status_code', None)
        return int(value) if value is not None else None


class MixinTestCase(testing.AsyncHTTPTestCase):

    def setUp(self):
        super(MixinTestCase, self).setUp()
        self.correlation_id = str(uuid.uuid4())
        self.mixin = self.create_mixin()

    def get_app(self):
        return web.Application([(r'/(.*)', TestHandler)],
                               **{'service': 'test', 'version': '0.1.0'})

    def create_mixin(self, add_correlation=True):
        mixin = http.HTTPClientMixin()
        mixin.application = self._app
        mixin.request = httputil.HTTPServerRequest(
            'GET', 'http://test:9999/test',
            headers=httputil.HTTPHeaders(
                {'Correlation-ID': self.correlation_id} if
                add_correlation else {}))
        return mixin

    @testing.gen_test()
    def test_default_user_agent(self):
        mixin = http.HTTPClientMixin()
        response = yield mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'))
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(
            response.body['headers'].get('User-Agent'),
            'sprockets.mixins.http/{}'.format(http.__version__))

    @testing.gen_test()
    def test_default_user_agent_with_partial_config(self):
        del self._app.settings['version']
        response = yield self.mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'))
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(
            response.body['headers'].get('User-Agent'),
            'sprockets.mixins.http/{}'.format(http.__version__))

    @testing.gen_test()
    def test_socket_errors(self):
        with mock.patch(
                'tornado.httpclient.AsyncHTTPClient.fetch') as fetch:
            fetch.side_effect = OSError
            response = yield self.mixin.http_fetch(self.get_url('/test'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 599)
        self.assertEqual(response.attempts, 3)

    @testing.gen_test()
    def test_without_correlation_id_behavior(self):
        mixin = self.create_mixin(False)
        response = yield mixin.http_fetch(
            self.get_url('/error?status_code=502'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 502)
        self.assertEqual(response.attempts, 3)

    @testing.gen_test()
    def test_get(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'))
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(
            response.body['headers'].get('User-Agent'), 'test/0.1.0')
        self.assertDictEqual(response.body['args'],
                             {'foo': ['bar'], 'status_code': ['200']})

    @testing.gen_test()
    def test_post(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body={'foo': 'bar', 'status_code': 200})

        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(
            response.body['headers'].get('User-Agent'), 'test/0.1.0')
        self.assertDictEqual(response.body['body'],
                             {'foo': 'bar', 'status_code': 200})

    @testing.gen_test()
    def test_get_json(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test?foo=bar&status_code=200'),
            request_headers={'Accept': 'application/json'})

        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(
            response.body['headers'].get('User-Agent'), 'test/0.1.0')
        self.assertDictEqual(response.body['args'],
                             {'foo': ['bar'], 'status_code': ['200']})

    @testing.gen_test()
    def test_post_html(self):
        expectation = '<html>foo</html>'
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body=expectation,
            request_headers={'Accept': 'text/html',
                             'Content-Type': 'text/html'})
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(
            response.body['headers'].get('User-Agent'), 'test/0.1.0')
        self.assertEqual(response.body['body'], expectation)

    @testing.gen_test()
    def test_post_json(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body={'foo': 'bar', 'status_code': 200},
            request_headers={'Accept': 'application/json',
                             'Content-Type': 'application/json'})

        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(
            response.body['headers'].get('User-Agent'), 'test/0.1.0')
        self.assertDictEqual(response.body['body'],
                             {'foo': 'bar', 'status_code': 200})

    @testing.gen_test()
    def test_post_msgpack(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body={'foo': 'bar', 'status_code': 200},
            request_headers={'Accept': 'application/msgpack',
                             'Content-Type': 'application/msgpack'})
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(
            response.body['headers'].get('User-Agent'), 'test/0.1.0')
        self.assertDictEqual(response.body['body'],
                             {'foo': 'bar', 'status_code': 200})

    @testing.gen_test()
    def test_post_pre_serialized_json(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body=json.dumps({'foo': 'bar', 'status_code': 200}),
            request_headers={'Accept': 'application/json',
                             'Content-Type': 'application/json'})
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(
            response.body['headers'].get('User-Agent'), 'test/0.1.0')
        self.assertDictEqual(response.body['body'],
                             {'foo': 'bar', 'status_code': 200})

    @testing.gen_test()
    def test_post_pre_serialized_msgpack(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/test'),
            method='POST',
            body=umsgpack.packb({'foo': 'bar', 'status_code': 200}),
            request_headers={'Accept': 'application/msgpack',
                             'Content-Type': 'application/msgpack'})
        self.assertTrue(response.ok)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body['headers'].get('Correlation-Id'),
                         self.correlation_id)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(
            response.body['headers'].get('User-Agent'), 'test/0.1.0')
        self.assertDictEqual(response.body['body'],
                             {'foo': 'bar', 'status_code': 200})

    @testing.gen_test()
    def test_rate_limiting_behavior(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/error?status_code=429'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 429)
        self.assertEqual(response.attempts, 3)

    @testing.gen_test()
    def test_error_response(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/error?status_code=400&message=Test%20Error'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 400)
        self.assertEqual(response.attempts, 1)
        self.assertEqual(response.body, 'Test Error')

    @testing.gen_test()
    def test_error_retry(self):
        response = yield self.mixin.http_fetch(
            self.get_url('/error?status_code=502'))
        self.assertFalse(response.ok)
        self.assertEqual(response.code, 502)
        self.assertEqual(response.attempts, 3)
        self.assertEqual(response.body, b'')

    @testing.gen_test()
    def test_unsupported_content_type(self):
        with self.assertRaises(ValueError):
            yield self.mixin.http_fetch(
                self.get_url('/test'),
                method='POST',
                body=['foo', 'bar'],
                request_headers={'Content-Type': 'text/html'})

    @testing.gen_test()
    def test_unsupported_accept(self):
        expectation = '<html>foo</html>'
        response = yield self.mixin.http_fetch(
                self.get_url('/test?content_type=text/html'),
                method='POST',
                body={'response': expectation},
                request_headers={'Accept': 'text/html',
                                 'Content-Type': 'application/json'})
        self.assertTrue(response.ok)
        self.assertEqual(response.headers['Content-Type'], 'text/html')
        self.assertEqual(response.body.decode('utf-8'), expectation)


