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

        class FnScope(object):
            suite = self
            expiry = datetime.now() + timedelta(seconds=3600)
            requested = 0

        scope = FnScope()

        def test_request(method, url, data=None, headers={}):
            scope.requested += 1
            auth = headers['Authorization']
            scope.suite.assertEqual(auth[:7], 'Bearer ')
            payload = jwt.decode(auth[7:], SAMPLE_KEY)  # decode the `Bearer` token
            scope.suite.assertEqual(payload['iss'], 666)
            scope.suite.assertEqual(payload['iat'] + 600, payload['exp'])
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
        pass

    def test_raw_request(self):
        pass

    def test_actual_request(self):
        pass
