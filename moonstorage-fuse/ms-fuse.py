import dataclasses
import datetime
import os
import errno
import stat
import threading
from stat import S_IFDIR
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
    until: datetime.datetime

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
        if path not in self.__files:
            return False

        file_info = self.__files[path]

        if file_info.until and datetime.datetime.now() >= file_info.until:
            return False

        return True

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
        self.__required_to_read_files = set()
        self.__buffer_to_write = dict()
        self.__now_created_files = dict()
        # End deprecated

        # New files storage implementation, all upper it is deprecated
        self.__files = FilesStorage()
        self.__release_lock = threading.Lock()

    def getattr(self, path, fh=None):
        logging.info(f"getattr called for path: {path}")

        if path == '/':
            return dict(st_mode=(S_IFDIR | 0o755), st_nlink=2)

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
                                      cid=file_info['cid'],
                                      until=datetime.datetime.now() + datetime.timedelta(seconds=2))

        return file_info['st']

    def read(self, path, size, offset, fh):
        logging.info(f'Reading file {path}...')

        if path not in self.__required_to_read_files:
            return

        file_info = self.__files[path]

        try:
            response = session.get(f'{self.base_url}/download/{file_info.cid}',
                                   params={'offset': offset,
                                           'chunk_size': size},
                                   timeout=3)
        except (Exception,) as e:
            logging.error(f'Can"t get chunk for: {path}: {e}')

            raise FuseOSError(errno.EIO)

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

        logging.info(f'Dir {path} content: {response.json()}')

        directory_contents = ['.', '..'] + response.json()

        self.__cache_in_memory.set(cache_key, directory_contents, datetime.timedelta(seconds=5))

        return directory_contents

    def create(self, path, mode, fi=None):
        logging.info(f'Created new file {path}!')

        self.__files[path] = FileInfo(st={
                'st_mode': stat.S_IFREG | 0o644,
                'st_nlink': 0,
                'st_size': 0,
                'st_ctime': time(),  # Время создания
                'st_mtime': time(),  # Время последнего изменения
                'st_atime': time(),  # Время последнего доступа
            }, cid=None, until=None)

        return 0

    def write(self, path, buf, offset, fh):
        logging.info(f'Writing a file {path} with fh {fh}...')

        buffer_path = f'{path}'

        if buffer_path not in self.__buffer_to_write:
            self.__buffer_to_write[buffer_path] = bytearray()

        if len(self.__buffer_to_write[buffer_path]) < offset + len(buf):
            self.__buffer_to_write[buffer_path].extend(bytearray(offset + len(buf) - len(self.__buffer_to_write[buffer_path])))

        self.__buffer_to_write[buffer_path][offset:offset + len(buf)] = buf

        self.__files[path].st['st_size'] += len(buf)

        return len(buf)

    def truncate(self, path, length, fh=None):
        path = f'{path}'

        if path not in self.__buffer_to_write:
            self.__buffer_to_write[path] = bytearray(length)
        else:
            self.__buffer_to_write[path] = self.__buffer_to_write[path][:length]

        return 0

    def release(self, path, fh):
        buffer_path = f'{path}'

        with self.__release_lock:
            if buffer_path in self.__buffer_to_write:
                url = f'{self.base_url}/upload'
                args = path[1:].split('/')

                if len(args) == 1:
                    raise FuseOSError(errno.EPERM)

                role, filename = args

                files = {'file': (filename, self.__buffer_to_write[buffer_path])}

                try:
                    logging.info(f'Uploading file {filename} with role {role}...')

                    response = session.post(url,
                                            files=files,
                                            timeout=30,
                                            data={'role': role})

                    logging.info(f'File {path} uploaded!')

                    if response.status_code != 200:
                        raise Exception(response.content.decode('utf-8'))

                except (Exception, ) as e:
                    logging.error(f'Can"t upload file {path}: {str(e)}')

                    raise FuseOSError(errno.EIO)

                self.__files[path].cid = response.json()['cid']

                del self.__buffer_to_write[buffer_path]

            return 0

    def unlink(self, path):
        logging.info(f'unlink called for path: {path}')

        if not self.__files.is_exists(path):
            raise FuseOSError(errno.ENOENT)

        # Отправка запроса на сервер для удаления файла
        response = session.post(f'{self.base_url}/delete', data={'path': path})

        if response.status_code != 200:
            logging.error(f'Failed to delete file: {path}, response: {response.content}')
            raise FuseOSError(errno.EIO)

        # Удаление информации о файле из локального кэша
        del self.__files[path]

        logging.info(f'File {path} successfully deleted')

    def rename(self, old, new, is_already_renamed: bool = False):
        logging.info(f"Renaming file from {old} to {new}...")

        if not self.__files.is_exists(old):
            raise FuseOSError(errno.ENOENT)

        self.release(old, None)

        # Отправка запроса на сервер для переименования файла
        response = session.put(f'{self.base_url}/rename', data={'old': old, 'new': new})

        if response.status_code != 200:
            logging.error(f'Failed to rename file: {old} to {new}, response: {response.content}')
            raise FuseOSError(errno.EIO)

        def _remove_if_exists(path):
            if self.__files.is_exists(path):
                del self.__files[path]

        # Обновление информации о файле в локальном кэше
        _remove_if_exists(old)
        _remove_if_exists(new)

        logging.info(f'File {old} successfully renamed to {new}')

        return 0


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
                './MoonStorage-2',
                foreground=True,
                ro=False,
                )
