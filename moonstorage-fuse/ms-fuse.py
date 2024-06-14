import os
import errno
import requests
from fuse import FUSE, Operations

import logging

import config

logging.basicConfig(level=logging.INFO)

session = requests.Session()


class HTTPApiFilesystem(Operations):
    def __init__(self, base_url):
        self.base_url = base_url
        self.cache = []

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        url = os.path.join(self.base_url, partial)
        return url

    def getattr(self, path, fh=None):
        logging.info(f"getattr called for path: {path}")

        response = session.get(f'{self.base_url}/fuse/info', params={'path': path})

        if response.status_code == 404:
            return -errno.ENOENT
        if response.status_code != 200:
            return -errno.EIO

        file_info = response.json()
        
        st = {
            'st_mode': file_info['mode'],
            'st_ino': file_info['ino'],
            'st_dev': file_info['dev'],
            'st_nlink': file_info['nlink'],
            'st_uid': file_info['uid'],
            'st_gid': file_info['gid'],
            'st_size': file_info['size'],
            'st_atime': file_info['atime'],
            'st_mtime': file_info['mtime'],
            'st_ctime': file_info['ctime'],
        }
        return st

    def read(self, path, size, offset, fh):
        path_parts = path[1:].split('/')

        if len(path_parts) == 1:
            return -errno.EISDIR

        headers = {'Range': f'bytes={offset}-{offset + size - 1}'}

        response = session.get(f'{self.base_url}/download_by_name/',
                               headers=headers,
                               params={'filename': path})
        if response.status_code != 206:
            return -errno.EIO

        logging.debug(f"read response status: {response.status_code}")

        return response.content

    def readdir(self, path, fh):
        url = f'{self.base_url}/fuse/dir/read{path}'

        logging.info(f"readdir called for path: {path}, URL: {url}")

        response = session.get(url)

        logging.info(f'Response from readdir: {response.content}')

        if response.status_code != 200:
            return -errno.EIO

        directory_contents = response.json()

        logging.debug(f"readdir response: {directory_contents}")

        return ['.', '..'] + directory_contents


if __name__ == '__main__':
    api_url = config.api_url
    username = config.username
    password = config.password
    db_host = config.db_host
    db_port = config.db_port
    ipfs_rpc_url = config.ipfs_rpc_url
    ipfs_api_url = config.ipfs_api_url

    session.put(f'{api_url}/init', data={'username': username,
                                         'password': password,
                                         'db_host': db_host,
                                         'db_port': db_port,
                                         'ipfs_rpc_url': ipfs_rpc_url,
                                         'ipfs_api_url': ipfs_api_url})

    fuse = FUSE(HTTPApiFilesystem(api_url), './mountpoint', foreground=True)
