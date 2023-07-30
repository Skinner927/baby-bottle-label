from __future__ import annotations

import configparser
import dataclasses
from typing import List


@dataclasses.dataclass
class Config:
    host: str
    port: int
    debug: bool
    baby_name: str
    alexa_app_id: List[str]
    label_size: List[str]
    rotate: int
    printer_name: str
    printer_media: str

    def __post_init__(self) -> None:
        # Ensure debug is bool
        if not isinstance(self.debug, bool):
            if isinstance(self.debug, str):
                self.debug = self.debug.lower() in ("1", "true", "yes")
            else:
                self.debug = False

        self.alexa_app_id = self._flat_str_list(self.alexa_app_id)
        self.label_size = self._flat_str_list(self.label_size)
        self.port = int(self.port)
        self.rotate = int(self.rotate)

    @classmethod
    def _flat_str_list(cls, seq) -> List[str]:
        if isinstance(seq, str):
            return [seq]
        if not isinstance(seq, list):
            return []
        new_list = []
        for item in seq:
            new_list.extend(cls._flat_str_list(item))
        return new_list

    @classmethod
    def read_ini(cls, ini: str) -> dict:
        parser = configparser.ConfigParser()
        try:
            parser.read(ini)
        except configparser.MissingSectionHeaderError:
            # Add a section for the ini file without a section
            with open(ini, "r") as f:
                ini_contents = "[whatever]\n" + f.read()
            parser = configparser.ConfigParser()
            parser.read_string(ini_contents, source=str(ini))
        config = dict()
        for name in parser.sections():
            config.update(parser[name])
        if not config:
            config.update(parser.defaults())
        return config


DEFAULT = Config(
    host="0.0.0.0",
    port=7788,
    debug=False,
    baby_name="",
    alexa_app_id=[],
    label_size=["600", "225"],
    rotate=0,
    printer_name="dymo450",
)
