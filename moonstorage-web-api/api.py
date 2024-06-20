import copy
import datetime
import json
import logging
import os
import pathlib
import stat
from functools import wraps
from time import time
from typing import Callable, NoReturn, Optional

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
                cursor.execute('select distinct name from registry '
                               'where role=%s and directory is null', (role_name,))

                files = [file[0] for file in cursor.fetchall()]

                cursor.execute('select distinct name from directories '
                               'where role=%s and parent_directory is null', (role_name,))

                directories = [directory[0] for directory in cursor.fetchall()]

                return files + directories

    @staticmethod
    def get_file_info_by_name(role: str, filename: str, directory_id: Optional[int] = None) -> dict:
        connection_args = auth_utils.get_connection_args()

        with psycopg2.connect(dbname="ipfs",
                              user=connection_args.username,
                              password=connection_args.password,
                              host=connection_args.db_host,
                              port=connection_args.db_port) as connection:
            with connection.cursor() as cursor:
                app.logger.info(f'Role: {role}\nFile name:{filename}')

                if directory_id is None:
                    cursor.execute('select file_size, uploaded_at, cid from registry '
                                   'where role=%s and name=%s and directory is null'
                                   ' order by uploaded_at desc', (role, filename))

                    found_file = cursor.fetchone()

                    if not found_file:
                        cursor.execute('select id from directories '
                                       'where role=%s and name=%s and parent_directory is null',
                                       (role, filename))

                        found_directory = cursor.fetchone()

                        if found_directory:
                            return {
                                'id': found_directory[0],
                                'is_dir': True
                            }
                        else:
                            raise FileNotFoundError()
                    else:
                        return {'size': found_file[0],
                                'uploaded_at': found_file[1],
                                'cid': found_file[2],
                                'is_dir': False}
                else:
                    app.logger.info(f'Trying to find file {filename} inside folder with id: {directory_id}')

                    cursor.execute('select file_size, uploaded_at, cid from registry '
                                   'where role=%s and name=%s and directory=%s'
                                   ' order by uploaded_at desc', (role, filename, directory_id))

                    found_file = cursor.fetchone()

                    if not found_file:
                        cursor.execute('select id from directories '
                                       'where role=%s and name=%s and parent_directory=%s',
                                       (role, filename, directory_id))

                        found_directory = cursor.fetchone()

                        if found_directory:
                            return {
                                'id': found_directory[0],
                                'is_dir': True
                            }
                        else:
                            raise FileNotFoundError()
                    else:
                        return {'size': found_file[0],
                                'uploaded_at': found_file[1],
                                'cid': found_file[2],
                                'is_dir': False}

    @staticmethod
    def check_if_directory_exists(role: str, directory_name: str) -> bool:
        connection_args = auth_utils.get_connection_args()

        with psycopg2.connect(dbname="ipfs",
                              user=connection_args.username,
                              password=connection_args.password,
                              host=connection_args.db_host,
                              port=connection_args.db_port) as connection:
            with connection.cursor() as cursor:
                cursor.execute('select count(*) from directories where role=%s and name=%s',
                               (role, directory_name))

                return cursor.fetchone()[0] > 0

    @staticmethod
    def get_directory_id(role: str, directory_name: str, parent_directory: int = None):
        connection_args = auth_utils.get_connection_args()

        with psycopg2.connect(dbname="ipfs",
                              user=connection_args.username,
                              password=connection_args.password,
                              host=connection_args.db_host,
                              port=connection_args.db_port) as connection:
            with connection.cursor() as cursor:
                if parent_directory is None:
                    cursor.execute('select id from directories '
                                   'where role=%s and name=%s and parent_directory is null',
                                   (role, directory_name))
                else:
                    cursor.execute('select id from directories '
                                   'where role=%s and name=%s and parent_directory=%s',
                                   (role, directory_name, parent_directory))

                return cursor.fetchone()[0]

    @staticmethod
    def check_if_file_is_available_in_ipfs(file_cid: str) -> bool:
        connection_args = auth_utils.get_connection_args()

        file_url = f'{connection_args.ipfs_api_url}/ipfs/{file_cid}'

        try:
            requests.get(file_url,
                         timeout=1,
                         headers={'Range': f'bytes=0-15'})
        except (Exception,):
            return False

        return True

    @staticmethod
    def get_files_in_directory(role: str, directory_id: int):
        connection_args = auth_utils.get_connection_args()

        with psycopg2.connect(dbname="ipfs",
                              user=connection_args.username,
                              password=connection_args.password,
                              host=connection_args.db_host,
                              port=connection_args.db_port) as connection:
            with connection.cursor() as cursor:
                cursor.execute('select distinct name from registry '
                               'where role=%s and directory=%s', (role, directory_id))

                files = [file[0] for file in cursor.fetchall()]

                cursor.execute('select distinct name from directories '
                               'where role=%s and parent_directory=%s', (role, directory_id))

                directories = [directory[0] for directory in cursor.fetchall()]

                return files + directories


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
    directory_id = request.form.get('directory_id')

    if 'file' not in request.files:
        raise Exception('Файл отсутствует!')

    file = request.files['file']

    if file.filename == '':
        raise Exception('Неправильное имя файла!')

    logging.info(f'Uploading a new file {file.filename} with role {required_role}...')

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

                if directory_id:
                    cursor.execute("insert into registry_data(cid, name, secret_key, role, file_size, file_hash, "
                                   "directory)"
                                   "values(%s, %s, %s, %s, %s, %s, %s)",
                                   (uploaded_file_cid, uploaded_filename, psycopg2.Binary(secret_key), required_role,
                                    uploaded_file_size, file_hash, directory_id))
                else:
                    cursor.execute("insert into registry_data(cid, name, secret_key, role, file_size, file_hash) "
                                   "values(%s, %s, %s, %s, %s, %s)",
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
                           'where cid=%s '
                           'order by uploaded_at desc', (file_cid,))

            found_file = cursor.fetchone()

            if found_file:
                filename, secret_key, file_cid = found_file[0], bytes(found_file[1]), found_file[2]

                file_url = f'{connection_args.ipfs_api_url}/ipfs/{file_cid}'

                offset = int(request.args.get('offset'))
                chunk_size = int(request.args.get('chunk_size'))
                offset_with_iv = offset + AES.block_size

                headers_for_chunk = {'Range': f'bytes={offset_with_iv}-{offset_with_iv + chunk_size - 1}'}
                headers_for_iv = {'Range': 'bytes=0-15'}

                try:
                    response_get_iv = requests.get(file_url,
                                                   headers=headers_for_iv,
                                                   timeout=2)
                    response_get_chunk = requests.get(file_url,
                                                      headers=headers_for_chunk,
                                                      timeout=2)
                except (Exception,) as e:
                    abort(404)

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

    def _make_default_dict_for_folder(directory_id: Optional[int] = None):
        return {
            'st': {
                'st_mode': stat.S_IFDIR | 0o755,
                'st_nlink': 2,
                'sn_size': 4096,
                'st_ctime': time(),  # Время создания
                'st_mtime': time(),  # Время последнего изменения
                'st_atime': time(),  # Время последнего доступа
            },
            'cid': None,
            'id': directory_id
        }

    app.logger.info(path_parts)

    if file_path == '/':
        return _make_default_dict_for_folder()
    elif len(path_parts) == 1:
        roles = HelperFuncs.get_user_roles()

        if path_parts[0] in roles:
            return _make_default_dict_for_folder()
        else:
            return 'Only roles is allowed by /', 404
    else:
        role = path_parts[0]
        file_name = path_parts[-1]
        search_directory_id = request.args.get('directory_id')

        app.logger.info(f'Path parts: {path_parts}')

        try:
            file_info = HelperFuncs.get_file_info_by_name(role, file_name, search_directory_id)

            if file_info['is_dir']:
                return _make_default_dict_for_folder(file_info['id'])
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
            'cid': file_info['cid'],
            'id': None,
        }


@app.route('/fuse/dir/read/', defaults={'dir_name': None})
@app.route('/fuse/dir/read/')
@auth_decorators.auth_required
def fuse_read_dir():
    dir_path = request.form.get('path')

    if dir_path == '/':
        return HelperFuncs.get_user_roles()

    dir_path_parts = dir_path[1:].split('/')

    if len(dir_path_parts) == 1:
        logging.info(dir_path_parts[0])

        return HelperFuncs.get_files_in_role(dir_path_parts[0])
    else:
        role = dir_path_parts[0]
        directory_id = int(request.form.get('directory_id'))

        return HelperFuncs.get_files_in_directory(role, directory_id)


@app.route('/fuse/file/exists')
@auth_decorators.auth_required
def fuse_check_file_exists():
    file_path = request.args.get('path')

    path_parts = file_path[1:].split('/')

    directory_id = request.args.get('directory_id')

    if len(path_parts) == 1:
        return False

    connection_args = auth_utils.get_connection_args()

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            if not directory_id:
                cursor.execute("select file_size from registry "
                               "where role=%s and name=%s and directory is null",
                               (path_parts[0], path_parts[-1]))
            else:
                cursor.execute("select file_size from registry "
                               "where role=%s and name=%s and directory=%s",
                               (path_parts[0], path_parts[-1], directory_id))

            found_file = cursor.fetchone()

            if not found_file:
                abort(404)
            else:
                return {'exists': True, 'size': found_file[0]}


@app.route('/delete', methods=['POST'])
@auth_decorators.auth_required
def remove_file():
    connection_args = auth_utils.get_connection_args()

    args = request.form.get('path')[1:].split('/')

    role, filename = args[0], args[-1]

    directory_id = request.form.get('directory_id')

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            if directory_id:
                cursor.execute('delete from registry '
                               'where role=%s and name=%s and directory=%s',
                               (role, filename, directory_id))
            else:
                cursor.execute('delete from registry '
                               'where role=%s and name=%s and directory is null',
                               (role, filename))

            return {'ok': True}


@app.route('/mkdir', methods=['POST'])
@auth_decorators.auth_required
def create_dir():
    connection_args = auth_utils.get_connection_args()

    path_parts = request.form.get('path')[1:].split('/')

    role, directory_path_parts = path_parts[0], path_parts[1]

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            if len(path_parts) == 1:
                cursor.execute('insert into directories_data(role, name) values(%s, %s)',
                               (role, path_parts[0]))
            else:
                directory_id = request.form.get('directory_id')

                logging.info(f'Trying to create folder: {directory_path_parts} with parent id: {directory_id}')

                cursor.execute('insert into directories_data(role, name, parent_directory) values(%s, %s, %s)',
                               (role, path_parts[-1], directory_id))

            return {'ok': True}


@app.route('/rename_dir', methods=['PUT'])
@auth_decorators.auth_required
def rename_dir():
    connection_args = auth_utils.get_connection_args()

    new_name = request.form.get('new').split('/')[-1]
    directory_id = request.form.get('directory_id')

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            cursor.execute('update directories set name=%s where id=%s',
                           (new_name, directory_id))

            return {'ok': True}


@app.route('/move', methods=['POST'])
@auth_decorators.auth_required
def move():
    connection_args = auth_utils.get_connection_args()

    args = request.args.get('filename')[1:].split('/')

    role, filename = args[0], args[-1]

    from_id = request.args.get('from_id')
    to_id = request.args.get('to_id')

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            app.logger.info(f'Move file {filename} from {from_id} to {to_id} in role {role}')

            # Исправить в будущем, кодировка шалит
            cursor.execute(f"update registry set directory={to_id if to_id else 'null'} where "
                           f"directory={from_id if from_id else 'null'} and role='{role}' and name='{filename}'")

            return {'ok': True}


@app.route('/rename', methods=['PUT'])
@auth_decorators.auth_required
def rename_file():
    connection_args = auth_utils.get_connection_args()

    args = request.args.get('old')[1:].split('/')

    role, filename = args[0], args[-1]
    new_name = request.args.get('new')[1:].split('/')[-1]

    directory_id = request.args.get('directory_id')

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            if directory_id:
                cursor.execute('update registry set name=%s '
                               'where role=%s and name=%s and directory=%s',
                               (new_name, role, filename, directory_id))
            else:
                cursor.execute('update registry set name=%s '
                               'where role=%s and name=%s and directory is null',
                               (new_name, role, filename))

            return {'ok': True}


@app.route('/rmdir', methods=['POST'])
@auth_decorators.auth_required
def rm_dir():
    connection_args = auth_utils.get_connection_args()

    directory_id = request.form.get('directory_id')

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            cursor.execute('delete from directories where id=%s',
                           (directory_id,))

            return {'ok': True}


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
