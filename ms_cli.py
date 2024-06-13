import argparse
import os

import psycopg2
from psycopg2.extensions import AsIs


def on_create_role(username: str, password: str, host: str, port: str, value: str) -> None:
    role_name = '_'.join(value.split())

    with psycopg2.connect(dbname="ipfs", user=username, password=password, host=host, port=port) as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(open(os.path.join('sqls', 'create_role.sql'), 'r').read()
                               .format(role_name=role_name))

                print(f'Роль успешно создана: {role_name}')
            except (Exception, ) as e:
                print(f'Не удалось создать роль: {str(e)}')


def on_create_user(username: str, password: str, host: str, port: str, value: str) -> None:
    new_username, new_password = value.split(':')

    with psycopg2.connect(dbname="ipfs", user=username, password=password, host=host, port=port) as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(open(os.path.join('sqls', 'create_user.sql'), 'r').read()
                               .format(username=new_username,
                                       password=new_password))

                print(f'Пользователь успешно создан: {new_username}')
            except (Exception, ) as e:
                print(f'Не удалось создать пользователя: {str(e)}')


def on_grant_access(username: str, password: str, host: str, port: str, value: str) -> None:
    username_to_grant, role_name = value.split(':')

    with psycopg2.connect(dbname="ipfs", user=username, password=password, host=host, port=port) as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(open(os.path.join('sqls', 'grant_access.sql'), 'r').read()
                               .format(role_name=role_name, username=username_to_grant))

                print(f'Пользователю "{username_to_grant}" успешно присвоена роль: {role_name}')
            except (Exception,) as e:
                print(f'Не удалось присвоить роль: {str(e)}')


commands_dict = {
    'create_role': on_create_role,
    'create_user': on_create_user,
    'grant_access': on_grant_access
}


def start_cli() -> None:
    parser = argparse.ArgumentParser(description='CLI для MoonStorage.')

    parser.add_argument('-user', dest='username')
    parser.add_argument('-password', dest='password')
    parser.add_argument('-host', dest='host', default='localhost')
    parser.add_argument('-port', dest='port', default=5432)

    parser.add_argument('--action', dest='action')
    parser.add_argument('value')

    args = parser.parse_args()

    commands_dict[args.action](args.username, args.password, args.host, args.port, args.value)


if __name__ == '__main__':
    start_cli()
