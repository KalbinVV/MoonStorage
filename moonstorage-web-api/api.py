import datetime
import json
import os
from functools import wraps
from typing import NamedTuple, Callable, NoReturn

import psycopg2
from flask import Flask, request, abort, make_response
import requests

from helper_classes import ConnectionArgs

from utils import auth_utils

from decorators import auth_decorators

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'upload/'


def get_value_from_form_or_raise_exception(key: str, exception_message: str) -> str | NoReturn:
    value = request.form.get(key)

    if not value:
        raise Exception(exception_message)

    return value


def wrap_to_valid_responses(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            response = func(*args, **kwargs)

            return json.dumps({'status': 'ok',
                               'result': response},
                              indent=4,
                              ensure_ascii=False).encode('utf-8')
        except (Exception,) as e:
            return json.dumps({'status': 'error',
                               'message': str(e)},
                              indent=4,
                              ensure_ascii=False).encode('utf-8')

    return wrapper


@app.route('/init', methods=['PUT'])
def init():
    try:
        username = get_value_from_form_or_raise_exception('username',
                                                          'Необходимо ввести имя пользователя!')
        password = get_value_from_form_or_raise_exception('password',
                                                          'Необходимо ввести пароль пользователя!')
        db_host = get_value_from_form_or_raise_exception('db_host',
                                                         'Необходимо ввести адрес хоста!')
        db_port = get_value_from_form_or_raise_exception('db_port',
                                                         'Необходимо ввести порт хоста!')
        ipfs_url = get_value_from_form_or_raise_exception('ipfs_url',
                                                          'Необходимо ввести адрес к rpc IFPS!')

        connection_args = ConnectionArgs(username=username,
                                         password=password,
                                         db_host=db_host,
                                         db_port=db_port,
                                         ipfs_url=ipfs_url)

        response = make_response(json.dumps({'status': 'ok'}).encode('utf-8'), 200)

        response.set_cookie('token', auth_utils.make_token(connection_args))

        return response
    except (Exception,) as e:
        abort(400, str(e))


@app.route('/roles', methods=['GET'])
@wrap_to_valid_responses
@auth_decorators.auth_required
def get_my_roles():
    connection_args = auth_utils.get_connection_args()

    with psycopg2.connect(dbname="ipfs",
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            cursor.execute('select role from public.user_roles;')

            return [role[0] for role in cursor.fetchall()]


@app.route('/files', methods=['GET'])
@wrap_to_valid_responses
@auth_decorators.auth_required
def get_available_files_list():
    connection_args = auth_utils.get_connection_args()

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            cursor.execute('select cid, filename, role from registry;')

            return [{'cid': file_info[0],
                     'filename': file_info[1],
                     'role': file_info[2]} for file_info in cursor.fetchall()]


@app.route('/upload_file', methods=['POST'])
@wrap_to_valid_responses
@auth_decorators.auth_required
def upload_file():
    connection_args = auth_utils.get_connection_args()

    required_role = get_value_from_form_or_raise_exception('role',
                                                           'Укажите роль, с которой добавляете файл!')

    if 'file' not in request.files:
        raise Exception('Файл отсутствует!')

    file = request.files['file']

    if file.filename == '':
        raise Exception('Неправильное имя файла!')

    uploaded_filename = f'{file.filename}-{str(datetime.datetime.now())}'

    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_filename)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(upload_path)

    with open(upload_path, 'rb') as f:
        response = requests.post(f'{connection_args.ipfs_url}/api/v0/add', files={'file': f}).json()

        uploaded_file_cid = response['Hash']

        with psycopg2.connect(dbname='ipfs',
                              user=connection_args.username,
                              password=connection_args.password,
                              host=connection_args.db_host,
                              port=connection_args.db_port) as connection:
            with connection.cursor() as cursor:
                cursor.execute("insert into registry_data(cid, filename, private_key, role) "
                               "values(%s, %s, %s, %s)",
                               (uploaded_file_cid, uploaded_filename, 'private_key', required_role))

                return {'cid': uploaded_file_cid}


@app.route('/', methods=['GET'])
@wrap_to_valid_responses
@auth_decorators.auth_required
def get_file():
    connection_args = auth_utils.get_connection_args()

    file_cid = get_value_from_form_or_raise_exception('cid',
                                                      'Укажите cid файла!')

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            cursor.execute('select cid, private_key from registry '
                           'where cid=%s', file_cid)

            found_file = cursor.fetchone()

            if found_file:
                pass
            else:
                abort(404)
