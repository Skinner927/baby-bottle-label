from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    baby_name: str
    alexa_app_id: List[str]
    label_size: List[str]
    rotate: int

    @classmethod
    def from_ini(cls, ini: str | Path) -> Config:
        parser = configparser.ConfigParser()
        parser.read(ini)
        config = dict()
        for name in parser.sections():
            config.update(parser[name])
        if not config:
            config.update(parser.defaults())
        parser.default_section


DEFAULT = Config(
    host="127.0.0.1",
    port=7788,
    debug=False,
    baby_name="<forgot baby-name!>",
    alexa_app_id=[],
    label_size=[],
    rotate=0,
)
