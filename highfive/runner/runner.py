from config import get_logger
from installation_manager import InstallationManager
from ..api_provider import GithubAPIProvider

import hashlib
import hmac
import json
import re

# Implementation of digest comparison from Django
# https://github.com/django/django/blob/0ed7d155635da9f79d4dd67e4889087d3673c6da/django/utils/crypto.py#L96-L105
def compare_digest(val_1, val_2):
    result = 0
    if len(val_1) != len(val_2):
        return False

    for x, y in zip(val_1, val_2):
        result |= ord(x) ^ ord(y)

    return result == 0


class HandlerError(object):
    '''Enum-like object solely for testing the payload handling result.'''

    NewInstallation  = 0
    UnregisteredRepo = 1
    DisabledEvent    = 2
    PayloadFromSelf  = 3


class Runner(object):
    '''
    Runner that receives incoming payloads from Github, verifies them, and
    passes them to the corresponding installation managers.
    '''
    def __init__(self, config):
        self.logger = get_logger(__name__)
        self.installations = {}
        self.config = config

    def verify_payload(self, x_hub_signature, raw_payload):
        '''
        This should be called to verify Github's webhook payload. This compares the
        'X-Hub-Signature' header value against the HMAC obtained from the payload
        using the app's "secret" key and a hash function.

        App "secret" key is optional, but it makes sure that you're getting payloads
        from Github. If a third-party found your POST endpoint, then anyone can send a
        cooked-up payload, and your bot will respond and make API requests to Github.

        In python, you can do something like this,
        >>> import random
        >>> print ''.join(map(chr, random.sample(range(32, 127), 32)))

        ... which will generate a 32-byte key in the ASCII range.
        '''

        try:    # All payloads are JSON - other payloads are ignored.
            payload = json.loads(raw_payload)
        except Exception as err:
            self.logger.debug('Cannot decode payload JSON: %s', err)
            return 400, None

        if self.config.secret:
            hash_func, signature = (x_hub_signature + '=').split('=')[:2]
            hash_func = getattr(hashlib, hash_func)     # This is generally `sha1`
            msg_auth_code = hmac.new(self.config.secret, raw_payload, hash_func)
            hashed = msg_auth_code.hexdigest()

            if not compare_digest(signature, hashed):
                self.logger.debug('Invalid signature!')
                return 403, None

            self.logger.info("Payload's signature has been verified!")
        else:
            self.logger.warn("Payload's signature can't be verified without secret key!")

        return None, payload

    def handle_payload(self, x_github_event, payload):
        '''
        Check (and filter) the incoming payloads, initialize managers (if required),
        and hook them with the API provider.
        '''

        inst_id = payload['installation']['id']
        self.logger.info('Received payload for installation %s'
                         '( event: %s, action: %s)' % (inst_id, x_github_event, payload.get('action')))
        # If this is a new installation event, ignore it.
        if 'installation_repositories' in x_github_event:
            return HandlerError.NewInstallation

        # If the installation doesn't exist, create a new manager for it.
        if self.installations.get(inst_id) is None:
            manager = InstallationManager(self.config.pem_key, self.config.integration_id, inst_id)
            self.installations[inst_id] = manager

        # Create an API provider for the payload
        manager = self.installations[inst_id]
        api = GithubAPIProvider(self.config, payload, api_json_request=manager.request)

        # Only accept payloads from registered repositories.
        if not any(re.search(pat, '%s/%s' % (api.owner, api.repo)) for pat in self.config.allowed_repos):
            self.logger.info('Rejected payload from %s/%s' % (api.owner, api.repo))
            self.installations.pop(inst_id)
            return HandlerError.UnregisteredRepo

        # If our handlers don't care about this event, then ignore this payload.
        if x_github_event not in self.config.enabled_events:
            self.logger.info("Payload doesn't match any enabled events. Skipping...")
            return HandlerError.DisabledEvent

        # Skip payloads sent by the bot itself.
        if self.config.name in api.sender:
            self.logger.info('Skipping payload sent by self')
            return HandlerError.PayloadFromSelf
