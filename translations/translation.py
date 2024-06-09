import json
from typing import Optional


class TranslationFile:
    def __init__(self, file_name: str):
        self.__file_name = file_name
        self.__read_json: Optional[dict[str, str]] = None

    def __read_json_file_if_not(self):
        if not self.__read_json:
            with open(self.__file_name, 'r') as f:
                self.__read_json = json.load(f)

    def get(self, key: str, **format_fields) -> str:
        self.__read_json_file_if_not()

        splitted_key = key.split('.')
        required_value = self.__read_json

        for part_of_key in splitted_key:
            required_value = required_value[part_of_key]

        if isinstance(required_value, list):
            return '\n'.join(map(lambda line: line.format(**format_fields),
                                 required_value))

        return str(required_value).format(**format_fields)
