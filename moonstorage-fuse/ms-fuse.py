import dataclasses
import datetime
import os
import errno
import stat
from time import time
from typing import Optional

import requests
from fuse import FUSE, Operations, FuseOSError

import logging

import config

from cache import CachedFieldsStorageInMemory, CachedFieldsStorageInFiles

logging.basicConfig(level=logging.INFO)

session = requests.Session()


@dataclasses.dataclass
class FileInfo:
    CONTENT_FOLDER = 'cache'

    st: dict[str, str | int | bytes]
    cid: Optional[str]

    @property
    def chunks_folder(self) -> str:
        folder = os.path.join(self.CONTENT_FOLDER, self.cid)
        os.makedirs(folder, exist_ok=True)

        return folder

    def get_chunk_path(self, offset: int, size: int) -> str:
        return os.path.join(self.chunks_folder, f'chunk:{offset}:{size}')

    def write_chunk(self, offset: int, size: int, value: bytes) -> None:
        with open(self.get_chunk_path(offset, size), 'wb') as f:
            f.write(value)

    def is_chunk_exists(self, offset: int, size: int):
        return os.path.exists(self.get_chunk_path(offset, size))

    def get_chunk(self, offset: int, size: int) -> bytes:
        with open(self.get_chunk_path(offset, size), 'rb') as f:
            return f.read()


class FilesStorage:
    def __init__(self):
        self.__files: dict[str, FileInfo] = dict()

    def is_exists(self, path: str) -> bool:
        return path in self.__files

    def __getitem__(self, path: str) -> FileInfo:
        return self.__files[path]

    def __setitem__(self, path: str, file_info: FileInfo) -> None:
        self.__files[path] = file_info

    def __delitem__(self, path: str) -> None:
        del self.__files[path]


class HTTPApiFilesystem(Operations):
    def __init__(self, base_url):
        self.base_url = base_url

        # Deprecated, should be removed
        self.__cache_in_memory = CachedFieldsStorageInMemory()
        self.__cache_in_files = CachedFieldsStorageInFiles('cache')
        self.__required_to_read_files = set()
        self.__buffer_to_write = dict()
        self.__now_created_files = dict()
        # End deprecated

        # New files storage implementation, all upper it is deprecated
        self.__files = FilesStorage()

    def getattr(self, path, fh=None):
        logging.info(f"getattr called for path: {path}")

        if self.__files.is_exists(path):
            return self.__files[path].st

        try:
            response = session.get(f'{self.base_url}/fuse/info',
                                   params={'path': path},
                                   timeout=2)

            if response.status_code == 404:
                raise FileNotFoundError()
        except (Exception,):
            logging.info(f'File {path} not found!')

            raise FuseOSError(errno.ENOENT)

        file_info = response.json()

        logging.info(f'FileInfo for {path}: {file_info}')

        self.__files[path] = FileInfo(st=file_info['st'],
                                      cid=file_info['cid'])

        return file_info['st']

    def read(self, path, size, offset, fh):
        logging.info(f'Reading file {path}...')

        file_info = self.__files[path]

        if file_info.is_chunk_exists(offset, size):
            return file_info.get_chunk(offset, size)

        try:
            response = session.get(f'{self.base_url}/download/{file_info.cid}',
                                   params={'offset': offset,
                                           'chunk_size': size},
                                   timeout=3)
        except (Exception,) as e:
            logging.error(f'Can"t get chunk for: {path}: {e}')

            raise FuseOSError(errno.EIO)

        file_info.write_chunk(offset, size, response.content)

        return response.content

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

    def chmod(self, path, mode):
        return 0

    def chown(self, path, uid, gid):
        return 0

    def create(self, path, mode, fi=None):
        logging.info(f'Created new file {path}!')

        self.__files[path] = FileInfo(st={
                'st_mode': stat.S_IFREG | 0o644,
                'st_nlink': 0,
                'st_size': 0,
                'st_ctime': time(),  # Время создания
                'st_mtime': time(),  # Время последнего изменения
                'st_atime': time(),  # Время последнего доступа
            }, cid=None)

        return 0

    def write(self, path, buf, offset, fh):
        logging.info(f'Writing a file {path}...')

        if path not in self.__buffer_to_write:
            self.__buffer_to_write[path] = bytearray()

        if len(self.__buffer_to_write[path]) < offset + len(buf):
            self.__buffer_to_write[path].extend(bytearray(offset + len(buf) - len(self.__buffer_to_write[path])))

        self.__buffer_to_write[path][offset:offset + len(buf)] = buf

        self.__files[path].st['st_size'] += len(buf)

        return len(buf)

    def truncate(self, path, length, fh=None):
        if path not in self.__cache_in_files:
            self.__buffer_to_write[path] = bytearray(length)
        else:
            self.__buffer_to_write[path] = self.__buffer_to_write[path][:length]

        return 0

    def flush(self, path, fh):
        if path in self.__buffer_to_write:
            url = f'{self.base_url}/upload'
            args = path[1:].split('/')

            if len(args) == 1:
                raise FuseOSError(errno.EIO)

            filename, role = args

            files = {'file': (filename, self.__buffer_to_write[path])}

            try:
                logging.info(f'Uploading file {filename} with role {role}...')

                response = session.post(url,
                                        files=files,
                                        timeout=5,
                                        data={'role': role})

                logging.info(f'File {path} uploaded!')

                if response.status_code != 200:
                    raise Exception(response.content.decode('utf-8'))

            except (Exception, ) as e:
                logging.error(f'Can"t upload file {path}: {str(e)}')

                raise FuseOSError(errno.EIO)

            del self.__buffer_to_write[path]
            del self.__files[path]

        return 0

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

    fuse = FUSE(HTTPApiFilesystem(api_url),
                './mountpoint',
                foreground=True)
