import argparse
import dataclasses
import datetime
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Tuple

import bottle
import PIL.Image
from bottle import post, request

from label.config import DEFAULT, Config
from label.generate import generate_image, parse_size

MONTHS = (
    ("January", "Jan"),
    ("February", "Feb"),
    ("March", "Mar"),
    ("April", "Apr"),
    ("May", "May"),
    ("June", "June"),
    ("July", "July"),
    ("August", "Aug"),
    ("September", "Sept"),
    ("October", "Oct"),
    ("November", "Nov"),
    ("December", "Dec"),
)

VALID_INTENTS = ("print", "print_qty", "print_date", "print_qty_date")

CONFIG = DEFAULT
DPI = 300


def get_safe(dic, *keys) -> Any:
    """Safely traverse through dictionary chains.

    :param dict dic:
    :param str keys:
    :return:
    """
    if not dic:
        return None
    no_d = dict()
    for key in keys:
        dic = dic.get(key, no_d)
    if dic is no_d:
        return None
    return dic


def response(msg) -> Dict[str, Any]:
    return dict(
        version="1.0",
        response=dict(
            outputSpeech=dict(
                type="PlainText",
                playBehavior="REPLACE_ENQUEUED",
                text=msg,
            ),
            shouldEndSession=True,
        ),
    )


# https://stackoverflow.com/a/52045942/721519
def date_th(num: int) -> str:
    date_suffix = ["th", "st", "nd", "rd"]

    if num % 10 in [1, 2, 3] and num not in [11, 12, 13]:
        return date_suffix[num % 10]
    else:
        return date_suffix[0]


@post("/")
def invoke_skill():
    # TODO: Prob should do verification of app ID since that's unique
    #  Need to get from either env or local conf file?
    try:
        return do_skill()
    except Exception:
        logging.exception("Unhandled exception")
        return response("Woah! I died!")


def do_skill():
    request_json = request.json
    if not request_json:
        return response("I could not understand your request.")
    if CONFIG.alexa_app_id and (
        get_safe(request_json, "session", "application", "applicationId")
        not in CONFIG.alexa_app_id
    ):
        return response("I don't know this application.")
    request_type = get_safe(request_json, "request", "type")
    if request_type == "SessionEndedRequest":
        # Just eat these
        return
    intent = get_safe(request.json, "request", "intent")
    if request_type != "IntentRequest" or not intent:
        return response("I don't understand your intent.")
    if intent.get("name", None) not in VALID_INTENTS:
        return response("I don't think you're asking a valid question.")
    slots = intent.get("slots", None)
    if not slots:
        return response("You're missing some important details.")

    quantity_str = get_safe(slots, "quantity", "value") or "1"
    date_str = (
        get_safe(slots, "date", "value")
        or datetime.datetime.now().isoformat().split("T")[0]
    )

    try:
        quantity = int(quantity_str)
        if quantity < 1:
            return response("Sorry, quantity cannot be less than 1.")
        if quantity > 10:
            return response(
                "Sorry, to prevent abuse I cannot print more than 10 labels."
            )
    except (TypeError, ValueError):
        return response("Sorry, I couldn't understand the number of labels to print.")

    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", date_str):
        year, month, day = m.groups()
        try:
            month_tuple = MONTHS[int(month) - 1]
        except (IndexError, ValueError, TypeError):
            return response("Sorry, I couldn't understand the month specified.")
    else:
        return response("Sorry, I couldn't understand the date to print.")

    return print_label(quantity, month_tuple, day)


def print_label(quantity: int, month_tuple: Tuple[str, str], day: str) -> dict:
    labels = "label" if quantity == 1 else "labels"
    say_request = f"{quantity} {labels} for {month_tuple[0]} {day}{date_th(int(day))}"

    # Generate the label
    if CONFIG.baby_name:
        text = [CONFIG.baby_name, f"{month_tuple[1]} {day}"]
    else:
        text = [f"{month_tuple[1]} {day}"]
    img = generate_image(
        ("\n".join(text)).strip(),
        image_size=parse_size(" ".join(CONFIG.label_size)),
        dpi=DPI,
        padding=parse_size("0.2em"),
        line_padding=parse_size("1.2em"),
        # TODO: rotate
    )
    if not img:
        return response(f"Sorry, I failed to make the {say_request}")
    ready = threading.Event()
    try:
        t = threading.Thread(
            target=print_thread_main, args=(img, ready, quantity), daemon=False
        )
        t.start()
        try:
            ready.wait(3.0)
        except TimeoutError:
            img.close()
            img = None
            return response(f"Sorry, I couldn't print the {say_request}")
    except BaseException:
        if img:
            img.close()
        raise
    # Not ours anymore
    img = None

    return response(f"Printing {say_request}")


def print_thread_main(
    img: PIL.Image.Image, ready: threading.Event, quantity: int
) -> None:
    with img:
        snap_common = (Path.home() / "snap/lprint/common").resolve()
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            img.save(fp=tmp, format="png")
            shutil.copy(tmp.name, "/tmp/last.png")
            ready.set()

            args = [
                "/snap/bin/lprint",
                "submit",
                *("-d", CONFIG.printer_name),
                *("-o", f"media={CONFIG.printer_media}"),
                *("-o", "print-darkness=100"),
                *("-n", str(quantity)),
                str(tmp.name),
            ]
            print(f"{args}")

            proc = subprocess.run(
                args,
                capture_output=True,
            )
            if proc.returncode != 0:
                log = logging.getLogger("label.server.print_thread_main")
                log.exception(
                    "Failed to print label! exit:%d\n  out: %s\n  err: %s",
                    proc.returncode,
                    proc.stdout.decode("utf-8"),
                    proc.stderr.decode("utf-8"),
                )
            else:
                print(proc.stdout.decode("utf-8"))
                print(proc.stderr.decode("utf-8"))


def main():
    global CONFIG
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", "-b", help=f"Default: {DEFAULT.host}")
    parser.add_argument("--port", "-p", help=f"Default: {DEFAULT.port}", type=int)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--app-id",
        action="extend",
        nargs="+",
        help="One or more Alexa applicationIds to filter requests by",
    )
    parser.add_argument(
        "--baby-name",
        help="baby name on label",
    )
    parser.add_argument(
        "--label-size",
        nargs=2,
        help=f"Specify the label size width and height in pixels. Multiply "
        f"inches by {DPI} (for {DPI} dpi) to get pixels. Should be passed as 2 "
        f"arguments: '100' '200' or '100px' '200px'.",
    )
    parser.add_argument(
        "--rotate",
        help=f"Degrees to rotate the label counterclockwise. "
        f"Use negative value for clockwise. Default: {DEFAULT.rotate}",
    )
    parser.add_argument("--printer-name")
    parser.add_argument(
        "--config", help="Path to config.ini file. Defaults to local config.ini."
    )
    args = parser.parse_args()

    cfg_dict = dataclasses.asdict(DEFAULT)
    if not args.config and os.path.exists("config.ini"):
        args.config = "config.ini"
    if args.config:
        cfg_dict.update(Config.read_ini(args.config))
    if args.host is not None:
        cfg_dict["host"] = args.host
    if args.port is not None:
        cfg_dict["port"] = args.port
    if args.debug is True:
        cfg_dict["debug"] = True
    if args.app_id:
        cfg_dict["alexa_app_id"] = args.app_id
    if args.baby_name is not None:
        cfg_dict["baby_name"] = args.baby_name
    if args.label_size:
        cfg_dict["label_size"] = args.label_size.join(" ")
    if args.rotate is not None:
        cfg_dict["rotate"] = args.rotate
    if args.printer_name:
        cfg_dict["printer_name"] = args.printer_name
    CONFIG = cfg = Config(**cfg_dict)

    bottle.run(host=cfg.host, port=cfg.port, debug=cfg.debug, reloader=cfg.debug)


# do not remove the application assignment (wsgi won't work)
application = bottle.default_app()

if __name__ == "__main__":
    main()
