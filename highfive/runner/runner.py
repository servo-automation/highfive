from config import get_logger

import hashlib
import hmac
import json

# Implementation of digest comparison from Django
# https://github.com/django/django/blob/0ed7d155635da9f79d4dd67e4889087d3673c6da/django/utils/crypto.py#L96-L105
def compare_digest(val_1, val_2):
    result = 0
    if len(val_1) != len(val_2):
        return False

    for x, y in zip(val_1, val_2):
        result |= ord(x) ^ ord(y)

    return result == 0


class Runner(object):
    '''
    Runner that receives incoming payloads from Github, verifies them, and
    passes them to the corresponding installation managers.
    '''
    def __init__(self, config):
        self.logger = get_logger(__name__)
        self.secret = config['secret']
        self.installations = {}
        self.config = config
        self.integration_id = int(config['integration_id'])

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

        if self.secret:
            hash_func, signature = (x_hub_signature + '=').split('=')[:2]
            hash_func = getattr(hashlib, hash_func)     # This is generally `sha1`
            msg_auth_code = hmac.new(self.secret, raw_payload, hash_func)
            hashed = msg_auth_code.hexdigest()

            if not compare_digest(signature, hashed):
                self.logger.debug('Invalid signature!')
                return 403, None

            self.logger.info("Payload's signature has been verified!")
        else:
            self.logger.warn("Payload's signature can't be verified without secret key!")

        return None, payload
