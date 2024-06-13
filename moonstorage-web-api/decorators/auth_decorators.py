from functools import wraps

from flask import request, abort

from utils import auth_utils


def auth_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        connection_args = auth_utils.get_connection_args()

        if connection_args is None:
            abort(403)

        return func(*args, **kwargs)

    return wrapper
