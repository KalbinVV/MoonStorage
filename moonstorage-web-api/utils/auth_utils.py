from typing import Type, Optional

import jwt

from flask import request, make_response

from helper_classes import ConnectionArgs


def make_token(connection_args: ConnectionArgs) -> str:
    encoded_jwt = jwt.encode(connection_args.to_json(), "secret", algorithm="HS256")

    return encoded_jwt


def decode_token(encoded_jwt: str) -> dict:
    return jwt.decode(encoded_jwt, "secret", algorithms=["HS256"])


def get_connection_args() -> ConnectionArgs:
    token = request.cookies.get('token')

    if token is None:
        return None

    try:
        decoded_jwt = jwt.decode(token, "secret", algorithms=["HS256"])

        return ConnectionArgs.from_json(decoded_jwt)
    except jwt.ExpiredSignatureError:
        return None
