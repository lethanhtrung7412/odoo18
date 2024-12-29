from odoo.odoo.tools._vendor import sessions
from odoo.odoo.tools import lazy_property
from odoo.odoo import http
from odoo.odoo.service import security
import base64
import json
import redis
import logging
import time
import os
import re
from hashlib import sha512

_logger = logging.getLogger(__name__)

SESSION_LIFETIME = 60 * 60 * 24 * 7 # 1 WEEK
_base64_urlsafe_re = re.compile(r'^[A-Za-z0-9_-]{84}$')


class RedisSessionStore(sessions.SessionStore):
    """Session store into Redis."""

    def __init__(self, session_class=None, renew_missing=False):
        super(RedisSessionStore, self).__init__(session_class)
        self.redis = redis.Redis("localhost", 6379, 0, decode_responses=True)
        self.renew_missing = renew_missing
        self._is_redis_server_running()

    def get_session_key(self, sid):
        return sid[:2]

    def save(self, session):
        if not self.is_valid_key(session.sid):
            raise ValueError(f'Invalid session id {session.sid!r}')
        session_key = self.get_session_key(session.sid)
        session_data = json.dumps(dict(session))

        try:
            self.redis.setex(session_key, SESSION_LIFETIME, session_data)
        except redis.RedisError as e:
            print(f"Error saving session to redis: {e}")

    def get(self, sid):
        if not self.is_valid_key(sid):
            return self.new()
        
        key = self.get_session_key(sid)
        try:
            session_data = self.redis.get(key)
            if session_data is None:
                _logger.debug("Can't found session in Redis. Using the empty session")
                if self.renew_missing:
                    return self.new()
                data = {}
            else:
                try:
                    data = json.loads(session_data)
                except Exception:
                    _logger.debug("Failed to decode session data from Redis. Using empty session.", exc_info=True)
                    data = {}
        except redis.RedisError as e:
            _logger.error(f"Error retrieving session from Redis: {e}", exc_info=True)
            data = {}

        return self.session_class(data, sid, False)

    def is_valid_key(self, key):
        return _base64_urlsafe_re.match(key) is not None 

    def delete(self, session):
        key = self.get_session_key(session.sid)
        try:
            self.redis.delete(key)
        except redis.RedisError as e:
            _logger.error(f"Error deleting session from Redis: {e}", exc_info=True)

    def list(self):
        try:
            cursor = 0
            result = []
            while True:
                cursor,key = self.redis.scan(cursor, match="*", count=100)
                result.extend(key)
                if cursor == 0:
                    break
            
            return [key.decode('utf-8') for key in result]
        except redis.RedisError as e:
            _logger.error(f"Error listing session in Redis: {e}", exc_info=True)
            return []

    def generate_key(self, salt=None):
        # The generated key is case sensitive (base64) and the length is 84 chars.
        # In the worst-case scenario, i.e. in an insensitive filesystem (NTFS for example)
        # taking into account the proportion of characters in the pool and a length
        # of 42 (stored part in the database), the entropy for the base64 generated key
        # is 217.875 bits which is better than the 160 bits entropy of a hexadecimal key
        # with a length of 40 (method ``generate_key`` of ``SessionStore``).
        # The risk of collision is negligible in practice.
        # Formulas:
        #   - L: length of generated word
        #   - p_char: probability of obtaining the character in the pool
        #   - n: size of the pool
        #   - k: number of generated word
        #   Entropy = - L * sum(p_char * log2(p_char))
        #   Collision ~= (1 - exp((-k * (k - 1)) / (2 * (n**L))))
        key = str(time.time()).encode() + os.urandom(64)
        hash_key = sha512(key).digest()[:-1]  # prevent base64 padding
        return base64.urlsafe_b64encode(hash_key).decode('utf-8')       
                
    def _is_redis_server_running(self):
        try:
            self.redis.ping()
        except redis.ConnectionError:
            raise redis.ConnectionError('Redis server is not responding')

    def session_gc(session_store):
        # Override to ignore file unlink
        # because sessions are not stored in files
        pass


# # class RedisApplication(Application)

http.root.session_store = RedisSessionStore(session_class=http.Session)