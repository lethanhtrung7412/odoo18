import redis
import logging
from odoo.tools.config import config
from odoo import api, models

_logger = logging.getLogger(__name__)


class RedisConnection(models.AbstractModel):
    _name = 'redis.connection'
    _description = 'Singleton Redis Connection'

    _redis = None

    @classmethod
    def get_redis(cls):
        if not cls._redis:
            try:
                redis_host = config.get('redis_host')
                redis_port = config.get('redis_port')
                redis_db_num = config.get('redis_db_num')

                if not redis_host or not redis_port or not redis_db_num:
                    raise ValueError("No redis configuraiton")
                
                cls._redis = redis.Redis(redis_host, redis_port, redis_db_num, decode_responses=True)
                cls._redis.ping() # check the connection
                _logger.info("Redis connection established")
            except redis.ConnectionError as e:
                _logger.error(f"Error connecting to Redis: {e}", exc_info=True)
                raise
            except ValueError as e:
                _logger.error(f"Invalid configuration: {e}", exc_info=True)
                raise
        return cls._redis