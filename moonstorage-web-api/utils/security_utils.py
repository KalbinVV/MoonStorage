from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util import Counter


def get_random_aes_key(key_length: int = 32) -> bytes:
    return get_random_bytes(key_length)


def encrypt_file(source_file_path: str,
                 dst_file_path: str,
                 aes_key: bytes,
                 blocks_sizes: int = 4096) -> None:
    # Генерируем случайный вектор инициализации (IV)
    iv = get_random_bytes(AES.block_size)

    initial_value = int.from_bytes(iv, byteorder='big')
    counter = Counter.new(128, initial_value=initial_value)

    cipher = AES.new(aes_key, AES.MODE_CTR, counter=counter)

    with open(source_file_path, 'rb') as source_file:
        with open(dst_file_path, 'wb') as encrypted_file:
            encrypted_file.write(iv)

            while True:
                chunk = source_file.read(blocks_sizes)

                if not chunk:
                    break

                encrypted_chunk = cipher.encrypt(chunk)

                encrypted_file.write(encrypted_chunk)


def decrypt_file(source_file_path: str,
                 dst_file_path: str,
                 aes_key: bytes,
                 blocks_sizes: int = 4096) -> None:
    with open(source_file_path, 'rb') as encrypted_file:
        with open(dst_file_path, 'wb') as decrypted_file:
            iv = encrypted_file.read(AES.block_size)

            # Создание счетчика для режима CTR с начальным значением на основе IV
            initial_value = int.from_bytes(iv, byteorder='big')
            counter = Counter.new(128, initial_value=initial_value)

            decipher = AES.new(aes_key, AES.MODE_CTR, counter=counter)

            while True:
                chunk = encrypted_file.read(blocks_sizes)

                if not chunk:
                    break

                decrypted_chunk = decipher.decrypt(chunk)

                decrypted_file.write(decrypted_chunk)


def decrypt_certain_chunk(aes_key: bytes,
                          iv: bytes,
                          offset: int,
                          chunk: bytes) -> bytes:
    initial_value = int.from_bytes(iv, byteorder='big')
    block_index = offset // AES.block_size
    adjusted_initial_value = initial_value + block_index
    counter = Counter.new(128, initial_value=adjusted_initial_value)

    decipher = AES.new(aes_key, AES.MODE_CTR, counter=counter)

    decrypted_chunk = decipher.decrypt(chunk)

    return decrypted_chunk
