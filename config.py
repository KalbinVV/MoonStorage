import os.path

ascii_art = r'''  .             *        .     .       .
       .     _     .     .            .       .
.    .   _  / |      .        .  *         _  .     .
        | \_| |                           | | __
      _ |     |                   _       | |/  |
     | \      |      ____        | |     /  |    \
     |  |     \    +/_\/_\+      | |    /   |     \
____/____\--...\___ \_||_/ ___...|__\-..|____\____/__
      .     .      |_|__|_|         .       .
   .    . .       _/ /__\ \_ .          .
      .       .    .           .         .'''

translation_file_path = os.path.join(os.path.join('translations', 'lang-files'), 'ru.json')

default_postgres_container_name = 'MoonStorage-Postgres'
default_postgres_port = 5432
default_postgres_username = 'admin'
default_postgres_password = 'password'
default_postgres_version = 'latest'

default_ipfs_container_name = 'MoonStorage-IPFS'
default_rpc_ipfs_port = 5001
default_webui_ipfs_port = 8080
default_node_ipfs_port = 4001
default_ipfs_version = 'latest'
default_ipfs_export_path = './export'
default_ipfs_data_path = './data'
default_ipfs_network_mode = 'private'
default_ipfs_node_mode = 'root'
default_ipfs_root_addr = '/ip4/ip_addr/tcp/tcp_ipfs_port/ipfs_node_id'

ipfs_scripts_folder_path = 'ipfs-scripts'

ipfs_init_private_child_script_path = os.path.join(os.path.join('templates', 'ipfs-scripts'),
                                                   'ipfs-node-init-private-child.sh')
ipfs_init_public_child_script_path = os.path.join(os.path.join('templates', 'ipfs-scripts'),
                                                  'ipfs-node-init-public-child.sh')

ipfs_init_private_root_script_path = os.path.join(os.path.join('templates', 'ipfs-scripts'),
                                                  'ipfs-node-init-private-root.sh')
ipfs_init_public_root_script_path = os.path.join(os.path.join('templates', 'ipfs-scripts'),
                                                 'ipfs-node-init-public-root.sh')

ipfs_init_result_path = os.path.join(os.path.join('ipfs-scripts', 'ipfs-node-init.sh'))

default_nginx_container_name = 'MoonStorage-Nginx'
default_nginx_webui_port = 80

docker_compose_template_private_root_path = os.path.join('templates', 'docker-compose-private-root.yml')
docker_compose_template_public_root_path = os.path.join('templates', 'docker-compose-public-root.yml')

docker_compose_template_private_children_path = os.path.join('templates', 'docker-compose-private-children.yml')
docker_compose_template_public_children_path = os.path.join('templates', 'docker-compose-public-children.yml')

result_docker_compose_path = 'docker-compose.yml'

nginx_conf_template_path = os.path.join('templates', 'nginx.conf')
result_nginx_conf_path = 'nginx.conf'

nginx_dockerfile_template_path = os.path.join('templates', 'nginx-dockerfile')
result_nginx_dockerfile_path = 'nginx-dockerfile'

couchdb_initializer_script_path = os.path.join('templates', 'couchdb-initializer.sh')
result_couchdb_initializer_script_path = 'couchdb-initializer.sh'

default_build_dir = 'build/'
