import argparse

import requests


def show_roles_list(api_url: str, session: requests.Session, user_input: str) -> None:
    response = session.get(f'{api_url}/roles', timeout=5)

    print(response.content.decode('utf-8'))


def show_files_list(api_url: str, session: requests.Session, user_input: str) -> None:
    response = session.get(f'{api_url}/files', timeout=5)

    print(response.content.decode('utf-8'))


def check_api_health(api_url: str, session: requests.Session, user_input: str) -> None:
    response = session.get(f'{api_url}/health', timeout=5)

    print(response.content.decode('utf-8'))


def upload_file(api_url: str, session: requests.Session, user_input: str) -> None:
    role = user_input.split(' ')[1]
    source_file = ''.join(user_input.split(' ')[2:])

    with open(source_file, 'rb') as f:
        response = session.post(f'{api_url}/upload_file',
                                files={'file': f},
                                data={'role': role})

        print(response.content.decode('utf-8'))


commands_dict = {
    '/roles': show_roles_list,
    '/files': show_files_list,
    '/health': check_api_health,
    '/upload': upload_file
}


def start_cli(api_url: str, session: requests.Session):
    username = input('Имя пользователя: ')
    password = input('Пароль пользователя: ')
    db_host = input('Адрес базы данных: ')
    db_port = input('Порт базы данных: ')
    ipfs_url = input('Адрес IPFS: ')

    try:
        response = session.put(f'{api_url}/init', data={'username': username,
                                                        'password': password,
                                                        'db_host': db_host,
                                                        'db_port': db_port,
                                                        'ipfs_url': ipfs_url})
        print(response.content)
    except (Exception,) as e:
        print(f'Не удалось подключиться: {str(e)}')

    while True:
        user_input = input('>')

        user_command = user_input.split(' ')[0]

        if user_input == '/q':
            break

        if user_command not in commands_dict:
            print('Неизвестная команда!')
        else:
            try:
                commands_dict[user_command](api_url, session, user_input)
            except (Exception, ) as e:
                print(f'!: {str(e)}')


def connect_to_api() -> None:
    parser = argparse.ArgumentParser(description='Admin CLI для MoonStorage.')

    parser.add_argument('--host', dest='host')

    args = parser.parse_args()

    session = requests.Session()

    try:
        session.get(f'{args.host}/health', timeout=5)
        start_cli(args.host, session)
    except (Exception,) as e:
        print(f'Не удалось подключиться: {e}')


if __name__ == '__main__':
    connect_to_api()
