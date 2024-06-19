import datetime
import json
import logging
import os
import pathlib
import stat
from functools import wraps
from time import time
from typing import Callable, NoReturn

import psycopg2
from Crypto.Cipher import AES
from flask import Flask, request, abort, make_response, send_file, after_this_request, Response
import requests

from helper_classes import ConnectionArgs

from utils import auth_utils, security_utils, hash_utils, file_utils

from decorators import auth_decorators

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'upload/'


class HelperFuncs:
    @staticmethod
    def get_user_roles() -> list:
        connection_args = auth_utils.get_connection_args()

        with psycopg2.connect(dbname="ipfs",
                              user=connection_args.username,
                              password=connection_args.password,
                              host=connection_args.db_host,
                              port=connection_args.db_port) as connection:
            with connection.cursor() as cursor:
                cursor.execute('select role from public.user_roles;')

                return [role[0] for role in cursor.fetchall()]

    @staticmethod
    def get_files_in_role(role_name: str) -> list:
        connection_args = auth_utils.get_connection_args()

        with psycopg2.connect(dbname="ipfs",
                              user=connection_args.username,
                              password=connection_args.password,
                              host=connection_args.db_host,
                              port=connection_args.db_port) as connection:
            with connection.cursor() as cursor:
                cursor.execute('select name from registry '
                               'where role=%s', (role_name,))

                return [file[0] for file in cursor.fetchall()]

    @staticmethod
    def get_file_info_by_name(role: str, filename: str) -> dict:
        connection_args = auth_utils.get_connection_args()

        with psycopg2.connect(dbname="ipfs",
                              user=connection_args.username,
                              password=connection_args.password,
                              host=connection_args.db_host,
                              port=connection_args.db_port) as connection:
            with connection.cursor() as cursor:
                app.logger.info(f'Role: {role}\nFile name:{filename}')

                cursor.execute('select file_size, uploaded_at, cid from registry '
                               'where role=%s and name=%s', (role, filename))

                found_file = cursor.fetchone()

                if not found_file:
                    raise FileNotFoundError()

                return {'size': found_file[0],
                        'uploaded_at': found_file[1],
                        'cid': found_file[2]}


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

            return json.dumps(response, indent=4, ensure_ascii=False).encode('utf-8')
        except (Exception,) as e:
            return abort(400, str(e))

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
        ipfs_rpc_url = get_value_from_form_or_raise_exception('ipfs_rpc_url',
                                                              'Необходимо ввести адрес к rpc IFPS!')
        ipfs_api_url = get_value_from_form_or_raise_exception('ipfs_api_url',
                                                              'Необходимо ввести адрес к api IFPS!')

        connection_args = ConnectionArgs(username=username,
                                         password=password,
                                         db_host=db_host,
                                         db_port=db_port,
                                         ipfs_rpc_url=ipfs_rpc_url,
                                         ipfs_api_url=ipfs_api_url)

        response = make_response(json.dumps({'status': 'ok'}).encode('utf-8'), 200)

        response.set_cookie('token', auth_utils.make_token(connection_args))

        return response
    except (Exception,) as e:
        abort(400, str(e))


@app.route('/roles', methods=['GET'])
@wrap_to_valid_responses
@auth_decorators.auth_required
def get_my_roles():
    return HelperFuncs.get_user_roles()


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
            cursor.execute('select cid, name, role from registry;')

            return [{'cid': file_info[0],
                     'filename': file_info[1],
                     'role': file_info[2]} for file_info in cursor.fetchall()]


@app.route('/upload', methods=['POST'])
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

    file_extension = pathlib.Path(file.filename).suffix

    uploaded_filename = f'{file.filename}'
    temp_filename = f'{file.filename}{datetime.datetime.now()}{file_extension}'

    temp_path = os.path.join('temp', temp_filename)
    os.makedirs('temp/', exist_ok=True)
    file.save(temp_path)

    file_hash = hash_utils.get_hash_of_file(temp_path)

    uploaded_file_size = os.path.getsize(temp_path)

    secret_key = security_utils.get_random_aes_key()

    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    security_utils.encrypt_file(temp_path,
                                upload_path,
                                secret_key)

    os.remove(temp_path)

    with open(upload_path, 'rb') as f:
        response = requests.post(f'{connection_args.ipfs_rpc_url}/api/v0/add', files={'file': f}).json()

        uploaded_file_cid = response['Hash']

        with psycopg2.connect(dbname='ipfs',
                              user=connection_args.username,
                              password=connection_args.password,
                              host=connection_args.db_host,
                              port=connection_args.db_port) as connection:
            with connection.cursor() as cursor:
                app.logger.debug(uploaded_file_cid)

                cursor.execute("insert into registry_data(cid, name, secret_key, role, file_size, file_hash, type) "
                               "values(%s, %s, %s, %s, %s, %s, 'file')",
                               (uploaded_file_cid, uploaded_filename, psycopg2.Binary(secret_key), required_role,
                                uploaded_file_size, file_hash))

                return {'cid': uploaded_file_cid,
                        'size': uploaded_file_size,
                        'hash': file_hash}


@app.route('/download/<file_cid>', methods=['GET'])
@auth_decorators.auth_required
def get_file(file_cid: str):
    connection_args = auth_utils.get_connection_args()

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            cursor.execute('select name, secret_key, cid from registry '
                           'where cid=%s', (file_cid,))

            found_file = cursor.fetchone()

            if found_file:
                filename, secret_key, file_cid = found_file[0], bytes(found_file[1]), found_file[2]

                file_url = f'{connection_args.ipfs_api_url}/ipfs/{file_cid}'

                offset = int(request.args.get('offset'))
                chunk_size = int(request.args.get('chunk_size'))
                offset_with_iv = offset + AES.block_size

                headers_for_chunk = {'Range': f'bytes={offset_with_iv}-{offset_with_iv + chunk_size - 1}'}
                headers_for_iv = {'Range': 'bytes=0-15'}

                response_get_iv = requests.get(file_url, headers=headers_for_iv)
                response_get_chunk = requests.get(file_url, headers=headers_for_chunk)

                os.makedirs('temp/', exist_ok=True)

                app.logger.info(f'Requested offset: {offset} and chunk_size: {chunk_size} for {filename}')

                iv = response_get_iv.content
                chunk = response_get_chunk.content

                required_chunk = security_utils.decrypt_certain_chunk(secret_key,
                                                                      iv,
                                                                      offset,
                                                                      chunk)

                return required_chunk

            else:
                abort(404)


@app.route('/fuse/info/')
@auth_decorators.auth_required
def fuse_get_file():
    file_path = request.args.get('path')

    path_parts = file_path[1:].split('/')

    default_dict_for_folder = {
        'st': {
            'st_mode': stat.S_IFDIR | 0o755,
            'st_nlink': 2,
            'sn_size': 4096,
            'st_ctime': time(),  # Время создания
            'st_mtime': time(),  # Время последнего изменения
            'st_atime': time(),  # Время последнего доступа
        },
        'cid': None
    }

    if file_path == '/':
        return default_dict_for_folder
    elif len(path_parts) == 1:
        roles = HelperFuncs.get_user_roles()

        if path_parts[0] in roles:
            return default_dict_for_folder
        else:
            return 'Only roles is allowed by /', 404
    else:
        role = path_parts[0]
        filename = path_parts[1]

        app.logger.info(f'Path parts: {path_parts}')

        try:
            file_info = HelperFuncs.get_file_info_by_name(role, filename)
        except (FileNotFoundError,):
            return '', 404

        return {
            'st': {
                'st_mode': stat.S_IFREG | 0o644,
                'st_nlink': 0,
                'st_size': file_info['size'],
                'st_ctime': time(),  # Время создания
                'st_mtime': time(),  # Время последнего изменения
                'st_atime': time(),  # Время последнего доступа
            },
            'cid': file_info['cid']
        }


@app.route('/fuse/dir/read/', defaults={'dir_name': None})
@app.route('/fuse/dir/read/<dir_name>')
@auth_decorators.auth_required
def fuse_read_dir(dir_name: str):
    if dir_name is None:
        return HelperFuncs.get_user_roles()
    else:
        return HelperFuncs.get_files_in_role(dir_name)


@app.route('/fuse/file/exists')
@auth_decorators.auth_required
def fuse_check_file_exists():
    file_path = request.args.get('path')

    path_parts = file_path[1:].split('/')

    if len(path_parts) == 1:
        return False

    connection_args = auth_utils.get_connection_args()

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select file_size from registry where role=%s and name=%s",
                           (path_parts[0], path_parts[1]))

            found_file = cursor.fetchone()

            if not found_file:
                abort(404)
            else:
                return {'exists': True, 'size': found_file[0]}


@app.route('/health', methods=['GET'])
def check_health():
    return 'alive'


if __name__ == '__main__':
    file_log = logging.FileHandler('logs.log')
    console_out = logging.StreamHandler()

    logging.basicConfig(handlers=(file_log, console_out),
                        format='[%(asctime)s | %(levelname)s]: %(message)s',
                        datefmt='%m.%d.%Y %H:%M:%S',
                        level=logging.DEBUG)

    app.run(host='0.0.0.0', port=5050, debug=True)

