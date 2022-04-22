import logging
from typing import Any, Optional, Protocol

from geventwebsocket.websocket import WebSocket

import json
import os
import sys
from json import JSONDecodeError

import bottle
from gevent.pywsgi import WSGIServer
from geventwebsocket import WebSocketError
from geventwebsocket.handler import WebSocketHandler
from lib.config_from_yaml import Config

cfg: Config
log = logging.getLogger("web server")
script_dir = os.path.dirname(os.path.realpath(__file__))
profile_path = os.path.join(script_dir, "storage", "profiles")


class WebCallbacks(Protocol):
    def run_profile(self, profile: Any, start_at_minute: float = 0) -> None:
        ...

    def abort_run(self) -> None:
        ...

    def add_observer(self, wsock: WebSocket) -> None:
        ...


class KilnServer(Protocol):
    def serve_forever(self):
        ...


class _KilnServer:
    _oven_callbacks: WebCallbacks
    _app: bottle.Bottle
    _server: WSGIServer

    def __init__(self, ip: str, port: int, callbacks: WebCallbacks) -> None:
        self._oven_callbacks = callbacks
        self._app = bottle.Bottle()
        self._setup_routing()
        self._server = WSGIServer((ip, port), self._app, handler_class=WebSocketHandler)

    def _setup_routing(self) -> None:
        self._app.route("/", callback=self.index)
        self._app.route("/kiln/<filename:path>", callback=self.send_static)
        self._app.route("/status", callback=self.handle_status)
        self._app.route("/config", callback=self.handle_config)
        self._app.route("/storage", callback=self.handle_storage)
        self._app.route("/control", callback=self.handle_control)
        self._app.post("/api", callback=self.handle_api)

    def serve_forever(self):
        self._server.serve_forever()

    @staticmethod
    def index():
        log.debug("handle index")
        return bottle.redirect('/kiln/index.html')

    def handle_api(self):
        log.info("/api is alive")
        log.info(bottle.request.json)

        # run a kiln schedule
        if bottle.request.json['cmd'] == 'run':
            wanted = bottle.request.json['profile']
            log.info('api requested run of profile = %s' % wanted)

            # start at a specific minute in the schedule
            # for restarting and skipping over early parts of a schedule
            start_at_minute = 0
            if 'startat' in bottle.request.json:
                start_at_minute = bottle.request.json['startat']
            # get the wanted profile/kiln schedule
            profile = find_profile(wanted)
            if not profile:
                return {"success": False, "error": "profile %s not found" % wanted}
            self._oven_callbacks.run_profile(profile, start_at_minute)

        if bottle.request.json['cmd'] == 'stop':
            log.info("api stop command received")
            self._oven_callbacks.abort_run()

        return {"success": True}

    @staticmethod
    def send_static(filename):
        log.debug("serving %s" % filename)
        return bottle.static_file(filename, root=os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "public"))

    def handle_control(self):
        wsock = get_websocket_from_request()
        log.info("websocket (control) opened")
        while True:
            try:
                message = wsock.receive()
                if message:
                    log.info("Received (control): %s" % message)
                    msgdict = json.loads(message)
                    if msgdict.get("cmd") == "RUN":
                        log.info("RUN command received")
                        profile_obj = msgdict.get('profile')
                        if profile_obj:
                            self._oven_callbacks.run_profile(profile_obj)
                    elif msgdict.get("cmd") == "SIMULATE":
                        log.info("SIMULATE command received")
                    elif msgdict.get("cmd") == "STOP":
                        log.info("Stop command received")
                        self._oven_callbacks.abort_run()
            except WebSocketError as e:
                log.error(e)
                break
        log.info("websocket (control) closed")

    @staticmethod
    def handle_storage():
        wsock = get_websocket_from_request()
        log.info("websocket (storage) opened")
        while True:
            try:
                message = wsock.receive()
                if not message:
                    break
                log.debug("websocket (storage) received: %s" % message)

                try:
                    msgdict = json.loads(message)
                except JSONDecodeError:
                    msgdict = {}

                if message == "GET":
                    log.info("GET command received")
                    wsock.send(get_profiles())
                elif msgdict.get("cmd") == "DELETE":
                    log.info("DELETE command received")
                    profile_obj = msgdict.get('profile')
                    if delete_profile(profile_obj):
                        msgdict["resp"] = "OK"
                    wsock.send(json.dumps(msgdict))
                elif msgdict.get("cmd") == "PUT":
                    log.info("PUT command received")
                    profile_obj = msgdict.get('profile')
                    force = True
                    if profile_obj:
                        if save_profile(profile_obj, force):
                            msgdict["resp"] = "OK"
                        else:
                            msgdict["resp"] = "FAIL"
                        log.debug("websocket (storage) sent: %s" % message)

                        wsock.send(json.dumps(msgdict))
                        wsock.send(get_profiles())
            except WebSocketError:
                break
        log.info("websocket (storage) closed")

    @staticmethod
    def handle_config():
        wsock = get_websocket_from_request()
        log.info("websocket (config) opened")
        while True:
            try:
                wsock.receive()
                wsock.send(get_config())
            except WebSocketError:
                break
        log.info("websocket (config) closed")

    def handle_status(self):
        wsock = get_websocket_from_request()
        self._oven_callbacks.add_observer(wsock)
        log.info("websocket (status) opened")
        while True:
            try:
                message = wsock.receive()
                wsock.send("Your message was: %r" % message)
            except WebSocketError:
                break
        log.info("websocket (status) closed")


def find_profile(wanted) -> Optional[Any]:
    """
    given a wanted profile name, find it and return the parsed
    json profile object or None.
    """
    # load all profiles from disk
    profiles = get_profiles()
    json_profiles = json.loads(profiles)

    # find the wanted profile
    for profile in json_profiles:
        if profile['name'] == wanted:
            return profile
    return None


def get_websocket_from_request() -> WebSocket:
    env = bottle.request.environ
    wsock: WebSocket = env.get('wsgi.websocket')
    if not wsock:
        bottle.abort(400, 'Expected WebSocket request.')
    return wsock


def get_profiles() -> str:
    try:
        profile_files = os.listdir(profile_path)
    except FileNotFoundError:
        profile_files = []
    profiles = []
    for filename in profile_files:
        with open(os.path.join(profile_path, filename), 'r') as f:
            profiles.append(json.load(f))
    return json.dumps(profiles)


def save_profile(profile, force=False) -> bool:
    profile_json = json.dumps(profile)
    filename = profile['name']+".json"
    filepath = os.path.join(profile_path, filename)
    if not force and os.path.exists(filepath):
        log.error("Could not write, %s already exists" % filepath)
        return False
    with open(filepath, 'w+') as f:
        f.write(profile_json)
        f.close()
    log.info("Wrote %s" % filepath)
    return True


def delete_profile(profile) -> bool:
    filename = profile['name']+".json"
    filepath = os.path.join(profile_path, filename)
    os.remove(filepath)
    log.info("Deleted %s" % filepath)
    return True


def get_config() -> str:
    return json.dumps(
        {
            "temp_scale": cfg.temp_scale,
            "time_scale_slope": cfg.time_scale_slope,
            "time_scale_profile": cfg.time_scale_profile,
            "kwh_rate": cfg.kwh_rate,
            "currency_type": cfg.currency_type
         }
    )


def create_web_server(cfg_: Config, callbacks: WebCallbacks) -> KilnServer:
    global cfg

    cfg = cfg_
    log.info("listening on %s:%d" % (cfg.listening_ip, cfg.listening_port))
    kiln_server = _KilnServer(cfg.listening_ip, cfg.listening_port, callbacks)
    return kiln_server
