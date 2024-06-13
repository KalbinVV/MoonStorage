import argparse

import requests


def show_roles_list(api_url, session: requests.Session) -> None:
    response = session.get(f'{api_url}/roles')

    print(response.content.decode('utf-8'))


commands_dict = {
    '/r': show_roles_list
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

        if user_input == '/q':
            break

        if user_input not in commands_dict:
            print('Неизвестная команда!')
        else:
            commands_dict[user_input](api_url, session)


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
