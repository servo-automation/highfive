from .. import event_handlers
from ..api_provider import GithubAPIProvider
from Queue import Queue
from config import get_logger
from datetime import datetime
from dateutil.parser import parse as datetime_parse
from jose import jwt
from request import request_with_requests
from time import sleep

import time

class InstallationManager(object):
    '''
    Manager that takes care of an installation. It's responsible for keeping
    the tokens in sync with Github API servers. It also exposes a `request` function
    that automatically blocks requests (once the API rate limit is reached), waits
    until the next window and continues the request.
    '''

    logger = get_logger(__name__)
    base_url = 'https://api.github.com'
    installation_url = base_url + '/installations/%s/access_tokens'
    rate_limit_url = base_url + '/rate_limit'
    headers = {
        'Content-Type': 'application/json',
        # integration-specific header
        'Accept': 'application/vnd.github.machine-man-preview+json',
        'Accept-Encoding': 'gzip, deflate'
    }

    def __init__(self, config, installation_id, store, json_request=request_with_requests):
        self.config = config
        self.installation_id = installation_id
        self.installation_url = self.installation_url % installation_id
        self.store = store

        # Objects for mocking in tests
        self.json_request = json_request

        # Stuff required for sync'ing token
        self.remaining = 0
        self.reset_time = int(time.time()) - 60
        self.next_token_sync = datetime.now()
        self.token = None
        self.queue = Queue()

    def sync_token(self):
        '''
        Prove your ownership over the integration to Github and request a token.
        This token is used for API requests in the future. It has a lifetime,
        and should be sync'ed again later.
        '''
        now = datetime.now(self.next_token_sync.tzinfo)     # timezone-aware version
        if now < self.next_token_sync:
            return

        self.logger.debug('Getting auth token with JWT from PEM key...')
        # https://developer.github.com/apps/building-github-apps/authentication-options-for-github-apps/
        since_epoch = int(time.time())
        auth_payload = {
            'iat': since_epoch,
            'exp': since_epoch + 600,       # 10 mins expiration for JWT
            'iss': self.config.integration_id,
        }

        auth = 'Bearer %s' % jwt.encode(auth_payload, self.config.pem_key, 'RS256')
        resp = self._request('POST', self.installation_url, auth=auth)
        self.token = resp.data['token']     # installation token (expires in 1 hour)
        self.logger.debug('Token expires on %s', resp.data['expires_at'])
        self.next_token_sync = datetime_parse(resp.data['expires_at'])

    def wait_time(self):
        '''
        Returns the wait time (in seconds) for the next request - this is based on the
        number of requests that can be raised in a given window.

        For example, if the request limit is 60/hour, then the waiting time for
        each request is 60 seconds. If the bot hasn't made any requests over the
        first half of an hour, then the wait time will now become 30 seconds.
        Hence, it's uniform.
        '''

        now = int(time.time())
        if now >= self.reset_time:
            resp = self._request('GET', self.rate_limit_url)
            self.reset_time = resp.data['rate']['reset']
            self.remaining = resp.data['rate']['remaining']
            self.logger.debug('Current time: %s, Remaining requests: %s, Reset time: %s',
                              now, self.remaining, self.reset_time)

        return (self.reset_time - now) / float(self.remaining)  # (uniform) wait time per request

    def _request(self, method, url, data=None, auth=True):
        '''
        Raw method used throughout the library. It's 'raw' because it doesn't
        care about the rate limits. It simply requests the server and gets you the
        response. Hence, this shouldn't be called by any of the handlers - which are
        concerned by the rate limits.

        By default, all requests are authenticated with the installation token. This can
        be overridden with a different `Authorization` header value, or can be disabled
        entirely (`auth=False`).
        '''

        if auth:
            self.headers['Authorization'] = ('token %s' % self.token) if auth is True else auth
        else:
            self.logger.debug('Making unauthenticated request...')

        self.logger.info('%s: %s (data: %s)', method, url, data)
        resp = self.json_request(method, url, data=data, headers=self.headers)
        if resp.code < 200 or resp.code >= 300:
            self.logger.error('Got a %s response: %r', resp.code, resp.data)
            raise Exception('Invalid response')

        if auth:
            self.headers.pop('Authorization')

        return resp

    def request(self, method, url, data=None, auth=True):
        '''
        Request method used in all the API calls for an installation. This ensures
        that we always have a valid token for making a request (and hence, we won't
        fail in auth), and distributes requests uniformly through a window (and hence,
        we won't gated by rate limits).
        '''
        self.sync_token()
        interval = self.wait_time()
        sleep(interval)
        resp = self._request(method=method, url=url, data=data, auth=auth)
        self.remaining -= 1
        return resp

    def clear_queue(self):
        '''Clear this manager's payload queue.'''

        while not self.queue.empty():
            (api, event) = self.queue.get()
            for _path, handler in event_handlers.get_handlers_for(event, cached=True):
                handler(api)

    def create_api_provider_for_payload(self, payload):
        api = GithubAPIProvider(self.config, payload, self.store,
                                api_json_request=self.request)
        return api
