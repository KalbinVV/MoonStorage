import abc
import datetime
import os
import errno
import requests
from fuse import FUSE, Operations

import logging

import config

from cache import CachedFieldsStorageInMemory, CachedFieldsStorageInFiles

logging.basicConfig(level=logging.INFO)

session = requests.Session()


class HTTPApiFilesystem(Operations):
    def __init__(self, base_url):
        self.base_url = base_url
        self.__cache_in_memory = CachedFieldsStorageInMemory()
        self.__cache_in_files = CachedFieldsStorageInFiles('cache')
        self.__required_to_read_files = set()

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        url = os.path.join(self.base_url, partial)
        return url

    def getattr(self, path, fh=None):
        logging.info(f"getattr called for path: {path}")

        cache_key = f'getattr-{path}'

        if self.__cache_in_memory.is_exist(cache_key):
            logging.info(f'getattr was read from cache: {path}')

            return self.__cache_in_memory.get(cache_key)

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

        self.__cache_in_memory.set(cache_key, st, datetime.timedelta(days=1))

        return st

    def __old_read(self, path, size, offset, fh):
        path_parts = path[1:].split('/')

        if len(path_parts) == 1:
            return -errno.EISDIR

        logging.info(f'Reading file {path}...')

        cache_key = f'read-{"_".join(path_parts)}'

        if self.__cache_in_files.is_exist(cache_key):
            logging.info(f'{path} was read from cache')

            return self.__cache_in_files.get(cache_key)

        response = session.get(f'{self.base_url}/download_by_name/',
                               params={'filename': path},
                               stream=True)

        if response.status_code != 200:
            return -errno.EIO

        blocks_size = 4096
        cached_file_path = os.path.join(self.__cache_in_files.cache_dir, '_'.join(path_parts))

        logging.info(f'Saving file {path}...')

        try:
            with open(cached_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=blocks_size):
                    f.write(chunk)

        except (Exception,) as e:
            logging.critical(f'Can"t save file {path}: {str(e)}')

        self.__cache_in_files.set(cache_key, cached_file_path, datetime.timedelta(days=1))

        logging.info(f'File {path} saved to cache')

        return self.__cache_in_files.get_with_offset(cache_key, offset, size)

    def read(self, path, size, offset, fh):
        if path not in self.__required_to_read_files:
            return -errno.EBADF

        logging.info(self.__required_to_read_files)

        path_parts = path[1:].split('/')

        if len(path_parts) == 1:
            return -errno.EISDIR

        logging.info(f'Reading file {path}...')

        cache_key = f'read-{"_".join(path_parts)}'

        if self.__cache_in_files.is_exist(cache_key):
            logging.info(f'{path} was read from cache')

            return self.__cache_in_files.get_with_offset(cache_key, offset, size)

        response = session.get(f'{self.base_url}/download_by_name/',
                               params={'filename': path},
                               stream=True)

        logging.info(f'Response status code from download by name: {response.status_code}')

        if response.status_code != 200:
            return -errno.EIO

        blocks_size = 4096
        cached_file_path = os.path.join(self.__cache_in_files.cache_dir, '_'.join(path_parts))

        logging.info(f'Saving file {path}...')

        try:
            with open(cached_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=blocks_size):
                    f.write(chunk)

        except (Exception,) as e:
            logging.critical(f'Can"t save file {path}: {str(e)}')

        self.__cache_in_files.set(cache_key, cached_file_path, datetime.timedelta(days=1))

        logging.info(f'File {path} saved to cache')

        return self.__cache_in_files.get_with_offset(cache_key, offset, size)

    def open(self, path, flags):
        logging.info(f'Trying to open a file: {path}...')

        url = f'{self.base_url}/fuse/file/exists'

        response = session.get(url,
                               params={'path': path})

        logging.info(f'Response code: {response.status_code}')

        if response.status_code == 404:
            return -errno.ENOENT
        elif response.status_code != 200:
            return -errno.EIO

        self.__required_to_read_files.add(path)

        return 0

    def opendir(self, path):
        logging.info(f'Trying to open a dir: {path}')

        return 0

    def readdir(self, path, fh):
        logging.info(f'Reading dir: {path}...')

        url = f'{self.base_url}/fuse/dir/read{path}'

        cache_key = f'readdir-{path}'

        if self.__cache_in_memory.is_exist(cache_key):
            logging.info(f'Dir {path} was read from cache')

            return self.__cache_in_memory.get(cache_key)

        response = session.get(url)

        if response.status_code != 200:
            return -errno.EIO

        directory_contents = ['.', '..'] + response.json()

        self.__cache_in_memory.set(cache_key, directory_contents, datetime.timedelta(minutes=1))

        return directory_contents

    def __del__(self):
        self.__cache_in_files.clear()


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
