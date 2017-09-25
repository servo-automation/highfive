from Queue import Queue
from datetime import datetime
from dateutil.parser import parse as datetime_parse
from jose import jwt
from time import sleep

from api_provider import GithubAPIProvider
from database import JsonStore, PostgreSql
from methods import AVAILABLE_EVENTS, get_handlers, get_logger

import hashlib, hmac, itertools, json, os, time, requests

WORKER_SLEEP_SECS = 1
SYNC_HANDLER_SLEEP_SECS = 3600
CONTRIBUTORS_UPDATE_INTERVAL_HOURS = 5

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
    headers = {
        'Content-Type': 'application/json',
        # integration-specific header
        'Accept': 'application/vnd.github.machine-man-preview+json',
        'Accept-Encoding': 'gzip, deflate'
    }

    def __init__(self, runner, inst_id):
        self.runner = runner
        self.logger = runner.logger
        self._id = inst_id
        self.installation_url = self.installation_url % inst_id
        # Github offers 5000 requests per hour (per installation) for an integration
        # (all these will be overridden once we sync the token with "/rate_limit" endpoint)
        api_data = self.runner.config.get(inst_id, {})
        self.remaining = api_data.get('remaining', 0)
        self.reset_time = api_data.get('reset', int(time.time()) - 60)
        self.next_token_sync = datetime_parse(api_data.get('expires_at', '%s' % datetime.now()))
        self.token = api_data.get('token')

    def sync_token(self):
        now = datetime.now(self.next_token_sync.tzinfo)     # should be timezone-aware version
        if now >= self.next_token_sync:
            self.logger.debug('Getting auth token with JWT from PEM key...')
            # https://developer.github.com/early-access/integrations/authentication/#jwt-payload
            since_epoch = int(time.time())
            auth_payload = {
                'iat': since_epoch,
                'exp': since_epoch + 600,       # 10 mins expiration for JWT
                'iss': self.runner.integration_id,
            }

            auth = 'Bearer %s' % jwt.encode(auth_payload, self.runner.pem_key, 'RS256')
            resp = self._request('POST', self.installation_url, auth=auth)
            self.token = resp['token']      # installation token (expires in 1 hour)
            self.logger.debug('Token expires on %s', resp['expires_at'])
            self.next_token_sync = datetime_parse(resp['expires_at'])

    def wait_time(self):
        now = int(time.time())
        if now >= self.reset_time:
            data = self._request('GET', self.rate_limit_url)
            self.reset_time = data['rate']['reset']
            self.remaining = data['rate']['remaining']
            self.logger.debug('Current time: %s, Remaining requests: %s, Reset time: %s',
                              now, self.remaining, self.reset_time)
        return (self.reset_time - now) / float(self.remaining)          # (uniform) wait time per request

    # NOTE: Not supposed to be called by any handler.
    def _request(self, method, url, data=None, auth=True,
                 headers_required=False):
        if auth:
            self.headers['Authorization'] = ('token %s' % self.token) if auth is True else auth
        else:
            self.logger.info('Making an unauthenticated request...')
        data = json.dumps(data) if data is not None  else data
        req_method = getattr(requests, method.lower())              # hack
        self.logger.info('%s: %s (data: %s)', method, url, data)
        resp = req_method(url, data=data, headers=self.headers)
        data, code = resp.text, resp.status_code

        if code < 200 or code >= 300:
            self.logger.error('Got a %s response: %r', code, data)
            raise Exception

        try:
            data = json.loads(data)
        except (TypeError, ValueError):         # stuff like 'diff' will be a string
            self.logger.debug('Cannot decode JSON, Passing the payload as string...')

        return (resp.headers, data) if headers_required else data

    def update_config(self):
        self.runner.config[self._id] = {
            'remaining': self.remaining,
            'expires_at': '%s' % self.next_token_sync,
            'reset': self.reset_time,
            'token': self.token,
        }

    def queue_request(self, method, url, data=None, auth=True,
                      headers_required=False):
        self.sync_token()
        interval = self.wait_time()
        sleep(interval)
        self.remaining -= 1
        self.update_config()
        return self._request(method=method, url=url, data=data, auth=auth,
                             headers_required=headers_required)

    # This is where we create the GithubAPIProvider and patch it
    # appropriately so that we cache the frequently used data.
    def create_api_provider_for_payload(self, payload):
        api = GithubAPIProvider(self.runner.name, payload, self.queue_request)

        # Sync the contributors for the given installation
        data = self.runner.db.get_obj(inst_id, 'contributors')
        interval = CONTRIBUTORS_UPDATE_INTERVAL_HOURS * 60 * 60
        cur_time = int(time.time())
        names = data.get('names', [])
        last_updated = data.get('last_updated', cur_time - 2 * interval)

        if cur_time > (last_updated + interval) or not names:
            names = api.get_contributors()
            data = {
                'last_updated': cur_time,
                'names': names,
            }
            self.runner.db.write_obj(data, inst_id, 'contributors')

        api.get_contributors = lambda: names
        return api

    def add(self, payload, event):
        api = self.create_api_provider_for_payload(payload)
        for _, handler in get_handlers(event):
            handler(api)


class SyncHandler(object):
    def __init__(self, inst_handler):
        self._id = inst_handler._id
        self.runner = inst_handler.runner   # FIXME: Too many indirections (refactor them someday)
        self.api_factory = inst_handler.create_api_provider_for_payload
        self.queue = Queue()

    def post(self, payload):
        self.queue.put(payload)

    def clear_queue(self):
        while not self.queue.empty():
            payload = self.queue.get()
            # Since these handlers don't belong to any particular event, they're supposed to
            # exist in `issues` and `pull_request` (with 'sync' flag enabled in their config)
            for path, handler in itertools.chain(get_handlers('issues', sync=True),
                                                 get_handlers('pull_request', sync=True)):
                # It's necessary to instantiate this class every time (since we could
                # monkey-patch along the way). There's one more way to "monkey-unpatch"
                # (by saving a snapshot of the class (its dict) and restoring it later)
                # but that could lead to *dangerous* code.
                api = self.api_factory(payload)
                handler(api, self.runner.db, self._id, os.path.basename(path))


class Runner(object):
    def __init__(self, config):
        self.name = config['name']
        self.logger = get_logger(__name__)
        self.enabled_events = config.get('enabled_events', [])
        self.integration_id = config['integration_id']
        self.secret = str(config.get('secret', ''))
        self.installations = {}
        self.sync_runners = {}
        self.config = config
        self.db = PostgreSql() if os.environ.get('DATABASE_URL') else JsonStore(config)

        if not self.enabled_events:
            self.enabled_events = AVAILABLE_EVENTS

        with open(config['pem_file'], 'r') as fd:
            self.pem_key = fd.read()

    def verify_payload(self, header_sign, raw_payload):
        try:
            payload = json.loads(raw_payload)
        except Exception as err:
            self.logger.debug('Cannot decode payload JSON: %s', err)
            return 400, None

        # app "secret" key is optional, but it makes sure that you're getting payloads
        # from Github. If a third-party found your POST endpoint, then anyone can send a
        # cooked-up payload, and your bot will respond and make API requests to Github.
        #
        # In python, you can do something like this,
        # >>> import random
        # >>> print ''.join(map(chr, random.sample(range(32, 127), 32)))
        #
        # ... which will generate a 32-byte key in the ASCII range.

        if self.secret:
            hash_func, signature = (header_sign + '=').split('=')[:2]
            hash_func = getattr(hashlib, hash_func)     # for now, sha1
            msg_auth_code = hmac.new(self.secret, raw_payload, hash_func)
            hashed = msg_auth_code.hexdigest()

            if not compare_digest(signature, hashed):
                self.logger.debug('Invalid signature!')
                return 403, None

            self.logger.info("Payload's signature has been verified!")
        else:
            self.logger.info("Payload's signature can't be verified without secret key!")

        return None, payload

    def set_installation(self, inst_id):
        self.installations.setdefault(inst_id, InstallationHandler(self, inst_id))
        inst_handler = self.installations[inst_id]
        self.sync_runners.setdefault(inst_id, SyncHandler(inst_handler))

    def check_installations(self):
        for _id in self.db.get_installations():
            self.set_installation(_id)

    def clear_queue(self):
        for sync_runner in self.sync_runners.itervalues():
            sync_runner.clear_queue()

    def handle_payload(self, payload, event):
        inst_id = payload['installation']['id']
        self.set_installation(inst_id)
        if event in self.enabled_events:
            if self.name in payload.get('sender', {'login': None})['login']:
                self.logger.debug('Skipping payload (for event: %s) sent by self', event)
            else:
                self.logger.info('Received payload for for installation %s'
                                 ' (event: %s, action: %s)', inst_id, event, payload.get('action'))
                self.installations[inst_id].add(payload, event)
        else:   # no matching events
            self.logger.info("(event: %s, action: %s) doesn't match any enabled events (installation %s)."
                             " Skipping payload-dependent handlers...", event, payload.get('action'), inst_id)
        # We pass all the payloads through sync handlers regardless of the event (they're unconstrained)
        self.sync_runners[inst_id].post(payload)    # will be queued and taken care of by the worker

    def poke_data(self):
        for _id, sync_runner in self.sync_runners.items():
            # poke all the sync handlers (of all installations) on hand with fake payloads
            self.logger.info('Poking handlers for installation %s with empty payload', _id)
            sync_runner.post({})

    def start_sync(self):
        self.logger.info('Spawning a new thread for sync handlers...')
        self.check_installations()
        next_check_time = int(time.time()) + SYNC_HANDLER_SLEEP_SECS

        while True:
            cur_time = int(time.time())
            if cur_time >= next_check_time:
                next_check_time += SYNC_HANDLER_SLEEP_SECS
                self.poke_data()

            sleep(WORKER_SLEEP_SECS)
            self.clear_queue()
