from datetime import datetime, timedelta
from dateutil.parser import parse as datetime_parse
from time import sleep

from api_provider import GithubAPIProvider
from methods import HANDLERS_DIR, get_handlers

import hashlib, hmac, json, os, time

TOKEN_TIMEOUT_SECS = 3600

# Implementation of digest comparison from Django
# https://github.com/django/django/blob/0ed7d155635da9f79d4dd67e4889087d3673c6da/django/utils/crypto.py#L96-L105
def compare_digest(val_1, val_2):
    result = 0
    if len(val_1) != len(val_2):
        return False

    for x, y in zip(val_1, val_2):
        result |= ord(x) ^ ord(y)

    return result == 0


class InstallationHandler(object):
    base_url = 'https://api.github.com'
    installation_url = base_url + '/installations/%s/access_tokens'
    rate_limit_url = base_url + '/rate_limit'
    # Github offers 5000 requests per hour (per installation) for an integration
    # (both of these will be overridden)
    remaining = 5000
    reset_time = 0

    last_token_sync = datetime.now() - timedelta(days=1)        # for first token sync
    headers = {
        'Content-Type': 'application/json',
        # integration-specific header
        'Accept': 'application/vnd.github.machine-man-preview+json',
        'Accept-encoding': 'gzip'
    }

    def __init__(self, runner, inst_id):
        self.runner = runner
        self.installation_url = self.installation_url % inst_id

    def sync_token(self):
        now = datetime.now()
        if (now - self.last_token_sync).seconds >= TOKEN_TIMEOUT_SECS:      # token expired
            # https://developer.github.com/early-access/integrations/authentication/#jwt-payload
            since_epoch = int(time.time())
            auth_payload = {
                'iat': since_epoch,
                'exp': since_epoch + 600,       # 10 mins expiration for JWT
                'iss': self.runner.integration_id,
            }

            auth = 'Bearer %s' % jwt.encode(auth_payload, self.runner.pem_key, 'RS256')
            resp = self._request(auth, 'POST', self.installation_url)
            dt = datetime_parse(resp['expires_at'])
            self.token = resp['token']      # installation token (expires in 1 hour)

    def wait_time_ms(self):
        now = int(time.time())
        if now >= self.reset_time:
            auth = 'token %s' % self.token
            data = self._request(auth, 'GET', self.rate_limit_url)
            self.reset_time = data['rate']['reset']
            self.remaining = data['rate']['remaining']
        return (now - self.reset_time) / self.remaining     # wait time per request

    def _request(self, auth, method, url, data=None):
        self.headers['Authorization'] = auth
        data = json.dumps(data) if data is not None  else data
        req_method = getattr(requests, method.lower())          # hack
        print '%s: %s (data: %s)' % (method, url, data)
        resp = req_method(url, data=data, headers=self.headers)
        data, code = resp.text, resp.status_code

        if code < 200 or code >= 300:
            print 'Got a %s response: %r' % (code, data)
            raise Exception

        if resp.headers.get('Content-Encoding') == 'gzip':
            try:
                fd = GzipFile(fileobj=StringIO(data))
                data = fd.read()
            except IOError:
                pass
        try:
            return json.loads(data)
        except (TypeError, ValueError):         # stuff like 'diff' will be a string
            return data

    def queue_request(self, method, url, data=None):
        self.sync_token()
        interval = self.wait_time_ms()
        sleep(interval)
        self.remaining -= 1
        auth = 'token %s' % self.token
        return self._request(auth, method, url, data)

    def add(self, payload, event):
        api = GithubAPIProvider(payload, self.queue_request)
        for _, handler in get_handlers(event):
            handler(api)


class Runner(object):
    def __init__(self, config):
        self.enabled_events = config.get('enabled_events', [])
        if not self.enabled_events:
            self.enabled_events = filter(os.path.isdir, os.listdir(HANDLERS_DIR))

        with open(config['pem_file'], 'r') as fd:
            self.pem_key = fd.read()
        self.integration_id = config['integration_id']
        self.secret = str(config.get('secret', ''))
        self.installations = {}

    def verify_payload(self, headers, raw_payload):
        try:
            payload = json.loads(raw_payload)
        except:
            return 400, None

        # app "secret" key is optional, but it makes sure that you're getting payloads
        # from Github. If a third-party found your POST endpoint, then anyone can send a
        # cooked-up payload, and your bot will respond make API requests.
        #
        # In python, you can do something like this,
        # >>> import random
        # >>> print ''.join(map(chr, random.sample(range(32, 127), 32)))
        #
        # ... which will generate a 32-byte key in the ASCII range.

        if self.secret:
            header_sign = headers.get('X-Hub-Signature', '') + '='
            hash_func, signature = header_sign.split('=')[:2]
            hash_func = getattr(hashlib, hash_func)     # for now, sha1
            msg_auth_code = hmac.new(self.secret, raw_payload, hash_func)
            hashed = msg_auth_code.hexdigest()

            if not compare_digest(signature, hashed):
                print 'Invalid signature!'
                return 403, None

            print "Payload's signature has been verified!"
        else:
            print "Payload's signature can't be verified without secret key!"

        event = headers['X-GitHub-Event'].lower()
        if event not in self.enabled_events:        # no matching events
            payload = None

        return None, payload

    def handle_payload(self, payload, event):
        inst_id = payload['installation']['id']
        self.installations.setdefault(inst_id, InstallationHandler(self, inst_id))
        self.installations[inst_id].add(payload, event)
