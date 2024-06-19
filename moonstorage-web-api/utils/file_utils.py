def generate_ino(path):
    return hash(path) & 0xFFFFFFFF
