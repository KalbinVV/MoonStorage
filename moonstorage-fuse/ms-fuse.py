from __future__ import with_statement

import sys

from fuse import FUSE, FuseOSError, Operations


class MoonStorageFS(Operations):
    def __init__(self):
        pass


def main():
    mount_point = sys.argv[0]

    FUSE(MoonStorageFS(), mount_point, nothreads=True, foreground=True)


if __name__ == '__main__':
    main()
