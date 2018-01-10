from highfive.runner.installation_manager import InstallationManager
from highfive.runner.request import Response

from datetime import datetime, timedelta
from jose import jwt
from unittest import TestCase

import time

# http://phpseclib.sourceforge.net/rsa/examples.html
SAMPLE_KEY='''-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQCqGKukO1De7zhZj6+H0qtjTkVxwTCpvKe4eCZ0FPqri0cb2JZfXJ/DgYSF6vUp
wmJG8wVQZKjeGcjDOL5UlsuusFncCzWBQ7RKNUSesmQRMSGkVb1/3j+skZ6UtW+5u09lHNsj6tQ5
1s1SPrCBkedbNf0Tp0GbMJDyR4e9T04ZZwIDAQABAoGAFijko56+qGyN8M0RVyaRAXz++xTqHBLh
3tx4VgMtrQ+WEgCjhoTwo23KMBAuJGSYnRmoBZM3lMfTKevIkAidPExvYCdm5dYq3XToLkkLv5L2
pIIVOFMDG+KESnAFV7l2c+cnzRMW0+b6f8mR1CJzZuxVLL6Q02fvLi55/mbSYxECQQDeAw6fiIQX
GukBI4eMZZt4nscy2o12KyYner3VpoeE+Np2q+Z3pvAMd/aNzQ/W9WaI+NRfcxUJrmfPwIGm63il
AkEAxCL5HQb2bQr4ByorcMWm/hEP2MZzROV73yF41hPsRC9m66KrheO9HPTJuo3/9s5p+sqGxOlF
L0NDt4SkosjgGwJAFklyR1uZ/wPJjj611cdBcztlPdqoxssQGnh85BzCj/u3WqBpE2vjvyyvyI5k
X6zk7S0ljKtt2jny2+00VsBerQJBAJGC1Mg5Oydo5NwD6BiROrPxGo2bpTbu/fhrT8ebHkTz2epl
U9VQQSQzY1oZMVX8i1m5WUTLPz2yLJIBQVdXqhMCQBGoiuSoSjafUhV7i1cEGpb88h5NBYZzWXGZ
37sJ5QsW+sJyoNde3xH8vdXhzU7eT82D6X/scw9RZz+/6rCJ4p0=
-----END RSA PRIVATE KEY-----'''


class InstallationManagerTests(TestCase):
    def check_default_headers(self, headers):
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(headers['Accept'],
                         'application/vnd.github.machine-man-preview+json')
        self.assertEqual(headers['Accept-Encoding'], 'gzip, deflate')

    def test_manager_init(self):
        manager = InstallationManager(key=SAMPLE_KEY,
                                      integration_id=666,
                                      installation_id=255)
        self.assertEqual(manager.token, None)
        # This triggers the manager to get the rate limit for the given window.
        self.assertTrue(manager.reset_time < time.time())
        # This flag triggers the manager to get the token during the first request
        self.assertTrue(manager.next_token_sync < datetime.now())
        self.assertTrue(manager.token is None)


    def test_token_sync(self):
        '''
        Initially, the manager doesn't have any token information, and so it
        tries to get the token. Here, we test its request object and token
        information that's later set on the manager.
        '''

        class FnScope(object):      # workaround to access outer scope vars
            expiry = datetime.now() + timedelta(seconds=3600)
            requested = 0

        scope = FnScope()

        def test_request(method, url, data, headers):
            self.check_default_headers(headers)
            self.assertEqual(method, 'POST')
            self.assertEqual(url, 'https://api.github.com/installations/255/access_tokens')
            scope.requested += 1
            auth = headers['Authorization']
            self.assertEqual(auth[:7], 'Bearer ')
            payload = jwt.decode(auth[7:], SAMPLE_KEY)  # decode the `Bearer` token
            self.assertEqual(payload['iss'], 666)
            self.assertEqual(payload['iat'] + 600, payload['exp'])
            return Response(data={
                'token': 'booya',
                # time-zone aware timestamp shouldn't raise exception
                # while comparing datetimes
                'expires_at': '%sZ' % scope.expiry
            })

        manager = InstallationManager(key=SAMPLE_KEY,
                                      integration_id=666,
                                      installation_id=255,
                                      json_request=test_request)
        manager.sync_token()
        self.assertEqual(scope.requested, 1)
        self.assertEqual(manager.next_token_sync.replace(tzinfo=None), scope.expiry)
        self.assertEqual(manager.token, 'booya')

        manager.sync_token()
        # This doesn't initiate syncing, because our token hasn't expired yet.
        self.assertEqual(scope.requested, 1)


    def test_wait_time(self):
        '''
        Wait time returns the waiting period (in seconds) for making a request.
        For this to work, it should get the remaining requests (that can be made
        in the window) from the API.
        '''

        class FnScope(object):
            reset = int(time.time()) + 3600

        scope = FnScope()

        def test_request(method, url, data, headers):
            self.check_default_headers(headers)
            self.assertEqual(headers['Authorization'], 'token booya')
            self.assertEqual(method, 'GET')
            self.assertEqual(url, 'https://api.github.com/rate_limit')
            return Response(data={      # Actual data from Github
                "rate": {
                    "limit": 5000,
                    "remaining": 4999,
                    "reset": scope.reset
                }
            })

        manager = InstallationManager(key=SAMPLE_KEY,
                                      integration_id=666,
                                      installation_id=255,
                                      json_request=test_request)
        # assume that we've obtained the token through `sync_token`
        manager.token = 'booya'
        self.assertTrue(manager.reset_time < time.time())
        wait_secs = manager.wait_time()
        self.assertTrue(wait_secs > 0.7 and wait_secs <= 0.75)  # 3600 / 5000 = 0.72
        self.assertEqual(manager.remaining, 4999)
        self.assertEqual(manager.reset_time, scope.reset)

        # assume that the bot hasn't made any requests for half an hour
        manager.reset_time -= 1800
        wait_secs = manager.wait_time()
        # wait time is now reduced by half
        self.assertTrue(wait_secs > 0.35 and wait_secs <= 0.38)


    def test_raw_request(self):
        '''
        Raw requests are authenticated by default, but they could also be
        unauthenticated.
        '''

        def test_request_default(method, url, data, headers):
            self.check_default_headers(headers)
            self.assertTrue(data is None)
            self.assertEqual(headers['Authorization'], 'token booya')
            self.assertEqual(method, 'SOME-METHOD')
            self.assertEqual(url, 'https://some.url')
            return Response(data={})

        def test_request_with_data(method, url, data, headers):
            self.check_default_headers(headers)
            self.assertEqual(data, {'foo': 'bar'})
            return Response(data={})

        def test_custom_auth(method, url, data, headers):
            self.check_default_headers(headers)
            self.assertEqual(headers['Authorization'], 'Some token')
            return Response(data={})

        def test_request_noauth(method, url, data, headers):
            self.check_default_headers(headers)
            self.assertEqual(headers.get('Authorization'), None)
            return Response(data={})

        def test_4xx_response(method, url, data, headers):
            return Response(data={}, code=400)

        manager = InstallationManager(key=SAMPLE_KEY,
                                      integration_id=666,
                                      installation_id=255,
                                      json_request=test_4xx_response)
        # assume that we've obtained the token through `sync_token`
        manager.token = 'booya'
        try:
            manager._request('SOME-METHOD', 'https://some.url')
            self.assertTrue(False)      # just to make this fail
        except Exception as err:
            self.assertEqual(str(err), 'Invalid response')

        test_cases = [
            (test_request_default, {}),
            (test_request_with_data, {'data': {'foo': 'bar'}}),
            (test_custom_auth, {'auth': 'Some token'}),
            (test_request_noauth, {'auth': False}),
        ]

        for function, kwargs in test_cases:
            manager.json_request = function
            manager._request('SOME-METHOD', 'https://some.url', **kwargs)


    def test_actual_request(self):
        manager = InstallationManager(key=SAMPLE_KEY,
                                      integration_id=666,
                                      installation_id=255)
        steps = []  # This is to ensure that the functions are called in the right order
        resp = Response(data={})

        manager.remaining = 10
        manager.sync_token = lambda: steps.append(0) or ()
        manager.wait_time = lambda: steps.append(1) or 0.001
        manager._request = lambda method, url, data, auth: steps.append(2) or resp

        self.assertEqual(manager.request('METHOD', 'URL'), resp)
        self.assertEqual(manager.remaining, 9)
        self.assertEqual(steps, [0, 1, 2])
