import random
import string


def generate_random_string(string_length: int):
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(string_length))
