import datetime
import json
import os
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
                cursor.execute("insert into registry_data(cid, filename, private_key, role) "
                               "values(%s, %s, %s, %s)",
                               (uploaded_file_cid, uploaded_filename, psycopg2.Binary(secret_key), required_role))

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
                           'where cid=%s', (file_cid, ))

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

                os.remove(temp_encrypt_path)

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


@app.route('/health', methods=['GET'])
def check_health():
    return 'alive'


def main():
    app.run(host='0.0.0.0', debug=True)


if __name__ == '__main__':
    main()
