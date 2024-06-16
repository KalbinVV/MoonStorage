import hashlib

BUF_SIZE = 65536


def get_hash_of_file(file_name: str) -> str:
    sha256 = hashlib.sha256()

    with open(file_name, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)

            if not data:
                break

            sha256.update(data)

    return sha256.hexdigest()
