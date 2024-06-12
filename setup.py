import ipaddress
import os

import config
from translations.translation import TranslationFile


def make_file_from_template(template_path: str,
                            result_file_path: str,
                            **fields):
    with open(template_path, 'r') as f:
        content = f.read().format(**fields)

    with open(result_file_path, 'w') as f:
        f.write(content)


def make_file_from_template_with_replace(template_path: str,
                                         result_file_path: str,
                                         **replacements):
    with open(template_path, 'r') as f:
        content = f.read()

    for key, value in replacements.items():
        content = content.replace(key, str(value))

    with open(result_file_path, 'w') as f:
        f.write(content)


def run_setup_cli():
    translation = TranslationFile(config.translation_file_path)

    print(translation.get('setup.start-title'))
    print(config.ascii_art)

    def _get_default_value_if_empty(value: str, default_value: str) -> str:
        value = value.strip()

        if len(value.strip()) == 0:
            return default_value

        return value

    def _enter_value(key: str, default_value: str, **fields) -> str:
        is_true_input = False

        value = ''

        while not is_true_input:
            value = input(translation.get(key,
                                          **fields))

            value = _get_default_value_if_empty(value,
                                                default_value)

            print(translation.get('setup.user-entered-value',
                                  user_input=value))

            user_choice = input(translation.get('setup.is_true_question'))

            if user_choice == 'y':
                is_true_input = True

        return value

    postgres_container_name = _enter_value('setup.postgres.container-name-input',
                                          config.default_postgres_container_name,
                                          default_container_name=config.default_postgres_container_name)
    postgres_version = _enter_value('setup.postgres.version-input',
                                   config.default_postgres_version,
                                   default_version=config.default_postgres_version)
    postgres_port = _enter_value('setup.postgres.port-input',
                                config.default_postgres_port,
                                default_port=config.default_postgres_port)
    postgres_admin_username = _enter_value('setup.postgres.admin-username-input',
                                          config.default_postgres_username,
                                          default_username=config.default_postgres_username)
    postgres_admin_password = _enter_value('setup.postgres.admin-password-input',
                                          config.default_postgres_password,
                                          default_password=config.default_postgres_password)

    ipfs_container_name = _enter_value('setup.ipfs.container-name-input',
                                       config.default_ipfs_container_name,
                                       default_container_name=config.default_ipfs_container_name)
    ipfs_rpc_port = _enter_value('setup.ipfs.rpc-port-input',
                                 config.default_rpc_ipfs_port,
                                 default_port=config.default_rpc_ipfs_port)
    ipfs_webui_port = _enter_value('setup.ipfs.webui-port-input',
                                   config.default_webui_ipfs_port,
                                   default_port=config.default_webui_ipfs_port)
    ipfs_node_port = _enter_value('setup.ipfs.node-port-input',
                                  config.default_node_ipfs_port,
                                  default_port=config.default_node_ipfs_port)
    ipfs_version = _enter_value('setup.ipfs.version-input',
                                config.default_ipfs_version,
                                default_version=config.default_ipfs_version)
    ipfs_export_folder = _enter_value('setup.ipfs.export-folder-name-input',
                                      config.default_ipfs_export_path,
                                      default_path=config.default_ipfs_export_path)
    ipfs_data_folder = _enter_value('setup.ipfs.data-folder-name-input',
                                    config.default_ipfs_data_path,
                                    default_path=config.default_ipfs_data_path)

    nginx_container_name = _enter_value('setup.nginx.container-name-input',
                                        config.default_nginx_container_name,
                                        default_container_name=config.default_nginx_container_name)
    nginx_webui_port = _enter_value('setup.nginx.webui-port',
                                    config.default_nginx_webui_port,
                                    default_port=config.default_nginx_webui_port)

    make_file_from_template(config.docker_compose_template_path,
                            config.result_docker_compose_path,
                            postgres_container_name=postgres_container_name,
                            postgres_version=postgres_version,
                            postgres_port=postgres_port,
                            postgres_admin_username=postgres_admin_username,
                            postgres_admin_password=postgres_admin_password,
                            ipfs_container_name=ipfs_container_name,
                            ipfs_version=ipfs_version,
                            ipfs_rpc_port=ipfs_rpc_port,
                            ipfs_webui_port=ipfs_webui_port,
                            ipfs_export_folder=ipfs_export_folder,
                            ipfs_data_folder=ipfs_data_folder,
                            result_nginx_dockerfile_path=config.result_nginx_dockerfile_path,
                            nginx_webui_port=nginx_webui_port,
                            nginx_container_name=nginx_container_name,
                            ipfs_node_port=ipfs_node_port,
                            result_couchdb_intiailizer_script_path=config.result_couchdb_initializer_script_path,
                            ipfs_scripts_folder_path=config.ipfs_scripts_folder_path)

    make_file_from_template_with_replace(config.nginx_conf_template_path,
                                         config.result_nginx_conf_path,
                                         WEBUI_PORT=ipfs_webui_port)

    make_file_from_template(config.nginx_dockerfile_template_path,
                            config.result_nginx_dockerfile_path)

    os.makedirs(config.ipfs_scripts_folder_path, exist_ok=True)

    make_file_from_template(config.ipfs_init_script_path,
                            config.ipfs_init_result_path)


if __name__ == '__main__':
    run_setup_cli()
