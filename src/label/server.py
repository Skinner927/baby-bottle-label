import argparse
import ast
import datetime
import os
import re
from pathlib import Path

import bottle
from bottle import post, request

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

APP_ID = os.getenv("APP_ID", None)
BABY_NAME


def load_config(config_path: str) -> None:
    global APP_ID
    file = Path(config_path)
    if not file.is_file():
        raise RuntimeError(f"Configuration not not a file: {config_path}")
    code = compile(
        file.read_bytes(),
        str(file),
        "exec",
    )
    scope = dict()
    exec(code, scope)
    if app_id := scope.get("APP_ID", None):
        APP_ID = app_id


def get_safe(dic, *keys):
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


def response(msg):
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

    request_json = request.json
    if not request_json:
        return response("I could not understand your request.")
    request_type = get_safe(request_json, "request", "type")
    if request_type == "SessionEndedRequest":
        # Just eat these
        return
    intent = get_safe(request.json, "request", "intent")
    if request_type != "IntentRequest" or not intent:
        return response("I could not understand your request.")
    if intent.get("name", None) not in VALID_INTENTS:
        return response("I could not understand your request.")
    slots = intent.get("slots", None)
    if not slots:
        return response("I could not understand your request.")

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

    labels = "label" if quantity == 1 else "labels"
    return response(
        f"Printing {quantity} {labels} for {month_tuple[0]} {day}{date_th(int(day))}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", "-b", default="127.0.0.1")
    parser.add_argument("--port", "-p", default=7788, type=int)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--config", help="path to config file")
    args = parser.parse_args()

    if args.config:
        load_config(args.config)

    bottle.run(host=args.host, port=args.port, debug=args.debug, reloader=args.debug)


# do not remove the application assignment (wsgi won't work)
application = bottle.default_app()

if __name__ == "__main__":
    main()
