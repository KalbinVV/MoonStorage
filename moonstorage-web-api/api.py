import datetime
import json
import logging
import os
import shutil
import stat
from functools import wraps
from typing import Callable, NoReturn

import psycopg2
from flask import Flask, request, abort, make_response, send_file, after_this_request
import requests

from helper_classes import ConnectionArgs

from utils import auth_utils, security_utils

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
                cursor.execute('select filename from registry '
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

                cursor.execute('select file_size from registry '
                               'where role=%s and filename=%s', (role, filename))

                found_file = cursor.fetchone()

                if not found_file:
                    raise FileNotFoundError()

                return {'size': found_file[0]}


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

    temp_path = os.path.join('temp', uploaded_filename)
    os.makedirs('temp/', exist_ok=True)
    file.save(temp_path)

    secret_key = security_utils.get_random_aes_key()

    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_filename)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    security_utils.encrypt_file(temp_path,
                                upload_path,
                                secret_key)

    os.remove(temp_path)

    with open(upload_path, 'rb') as f:
        response = requests.post(f'{connection_args.ipfs_rpc_url}/api/v0/add', files={'file': f}).json()

        uploaded_file_cid = response['Hash']
        uploaded_file_size = response['Size']

        with psycopg2.connect(dbname='ipfs',
                              user=connection_args.username,
                              password=connection_args.password,
                              host=connection_args.db_host,
                              port=connection_args.db_port) as connection:
            with connection.cursor() as cursor:
                cursor.execute("insert into registry_data(cid, filename, private_key, role, file_size) "
                               "values(%s, %s, %s, %s, %s)",
                               (uploaded_file_cid, uploaded_filename, psycopg2.Binary(secret_key), required_role,
                                uploaded_file_size))

                return {'cid': uploaded_file_cid,
                        'size': uploaded_file_size}


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
            cursor.execute('select filename, private_key from registry '
                           'where cid=%s', (file_cid,))

            found_file = cursor.fetchone()

            if found_file:
                filename, secret_key = found_file[0], bytes(found_file[1])

                file_url = f'{connection_args.ipfs_api_url}/ipfs/{file_cid}'

                response = requests.get(file_url)

                os.makedirs('temp/', exist_ok=True)

                temp_encrypt_path = os.path.join('temp', f'{filename}-encrypted')
                temp_decrypt_path = os.path.join('temp', filename)

                with open(temp_encrypt_path, 'wb') as encrypted_file:
                    encrypted_file.write(response.content)

                security_utils.decrypt_file(temp_encrypt_path,
                                            temp_decrypt_path,
                                            secret_key)

                # os.remove(temp_encrypt_path)
                # Вернуть после того как придумаю как сделать адекватную передачу данных через fuse

                # TODO: Сделать удаление файлов после расшифрования
                '''
                @after_this_request
                def remove_file(_rsp):
                    file_handle.close()
                    os.remove(temp_decrypt_path)
                '''

                return send_file(temp_decrypt_path, download_name=filename)

            else:
                abort(404)


@app.route('/download_by_name/', methods=['GET'])
@auth_decorators.auth_required
def get_file_by_name():
    filename = request.args.get('filename')

    app.logger.info(f'filename: {filename}')

    path_parts = filename[1:].split('/')

    connection_args = auth_utils.get_connection_args()

    with psycopg2.connect(dbname='ipfs',
                          user=connection_args.username,
                          password=connection_args.password,
                          host=connection_args.db_host,
                          port=connection_args.db_port) as connection:
        with connection.cursor() as cursor:
            cursor.execute('select filename, private_key, cid from registry '
                           'where role=%s and filename=%s', (path_parts[0], path_parts[1]))

            app.logger.info(f'Path parts: {path_parts}')

            found_file = cursor.fetchone()

            if found_file:
                filename, secret_key, file_cid = found_file[0], bytes(found_file[1]), found_file[2]

                file_url = f'{connection_args.ipfs_api_url}/ipfs/{file_cid}'

                response = requests.get(file_url)

                os.makedirs('temp/', exist_ok=True)

                temp_encrypt_path = os.path.join('temp', f'{filename}-encrypted')
                temp_decrypt_path = os.path.join('temp', filename)

                with open(temp_encrypt_path, 'wb') as encrypted_file:
                    encrypted_file.write(response.content)

                security_utils.decrypt_file(temp_encrypt_path,
                                            temp_decrypt_path,
                                            secret_key)

                @after_this_request
                def remove_file(rsp):
                    try:
                        os.remove(temp_decrypt_path)
                    except Exception as error:
                        app.logger.error("Error removing file: %s", error)
                    return rsp

                return send_file(temp_decrypt_path, download_name=filename)

            else:
                abort(404)


@app.route('/files_in_role/{role_name}')
@auth_decorators.auth_required
def get_files_in_role(role_name: str):
    HelperFuncs.get_files_in_role(role_name)


@app.route('/fuse/info/')
@auth_decorators.auth_required
def fuse_get_file():
    file_path = request.args.get('path')

    path_parts = file_path[1:].split('/')

    if len(path_parts) == 1:
        return {
            'mode': stat.S_IFDIR,
            'nlink': 0,
            'size': 1,
            "atime": 1625247600,
            "mtime": 1625247600,
            "ctime": 1625247600,
            "ino": 12345,
            "dev": 2049,
            "uid": 1000,
            "gid": 1000,
        }
    else:
        role = path_parts[0]
        filename = path_parts[1]

        app.logger.info(f'Path parts: {path_parts}')

        try:
            file_info = HelperFuncs.get_file_info_by_name(role, filename)
        except (FileNotFoundError, ):
            return '', 404

        return {
            'mode': stat.S_IFREG,
            'nlink': 0,
            'size': file_info['size'],
            "atime": 1625247600,
            "mtime": 1625247600,
            "ctime": 1625247600,
            "ino": 12345,
            "dev": 2049,
            "uid": 1000,
            "gid": 1000,
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
            cursor.execute("select file_size from registry where role=%s and filename=%s",
                           (path_parts[0], path_parts[1]))

            found_file = cursor.fetchone()

            if not found_file:
                abort(404)
            else:
                return {'exists': True, 'size': found_file[0]}


@app.route('/health', methods=['GET'])
def check_health():
    return 'alive'


def main():
    app.run(host='0.0.0.0', debug=True)

    shutil.rmtree(app.config['UPLOAD_FOLDER'])


if __name__ == '__main__':
    main()
