import logging
from functools import wraps

from flask import request, abort

from utils import auth_utils


def auth_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.debug(f'Trying to check if user can get access')

        connection_args = auth_utils.get_connection_args()

        if connection_args is None:
            logging.debug(f'User can"t get access!')

            abort(403)

        return func(*args, **kwargs)

    return wrapper
