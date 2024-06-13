import json
from typing import NamedTuple, Any


class ConnectionArgs(NamedTuple):
    username: str
    password: str
    db_host: str
    db_port: int
    ipfs_rpc_url: str
    ipfs_api_url: str

    def to_json(self):
        return {'username': self.username,
                'password': self.password,
                'db_host': self.db_host,
                'db_port': self.db_port,
                'ipfs_rpc_url': self.ipfs_rpc_url,
                'ipfs_api_url': self.ipfs_api_url}

    @staticmethod
    def from_json(json_dict: dict[str, Any]):
        return ConnectionArgs(username=json_dict['username'],
                              password=json_dict['password'],
                              db_host=json_dict['db_host'],
                              db_port=json_dict['db_port'],
                              ipfs_rpc_url=json_dict['ipfs_rpc_url'],
                              ipfs_api_url=json_dict['ipfs_api_url'])
