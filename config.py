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

default_couchdb_container_name = 'MoonStorage-CouchDB'
default_couchdb_port = 5984
default_couchdb_username = 'admin'
default_couchdb_password = 'password'
default_couchdb_version = 'latest'

default_ipfs_container_name = 'MoonStorage-IPFS'
default_rpc_ipfs_port = 5001
default_webui_ipfs_port = 8080
default_node_ipfs_port = 4001
default_ipfs_version = 'latest'
default_ipfs_export_path = './export'
default_ipfs_data_path = './data'

default_nginx_container_name = 'MoonStorage-Nginx'
default_nginx_webui_port = 80

docker_compose_template_path = os.path.join('templates', 'docker-compose-template.yml')
result_docker_compose_path = 'docker-compose.yml'

nginx_conf_template_path = os.path.join('templates', 'nginx.conf')
result_nginx_conf_path = 'nginx.conf'

nginx_dockerfile_template_path = os.path.join('templates', 'nginx-dockerfile')
result_nginx_dockerfile_path = 'nginx-dockerfile'

couchdb_initializer_script_path = os.path.join('templates', 'couchdb-initializer.sh')
result_couchdb_initializer_script_path = 'couchdb-initializer.sh'