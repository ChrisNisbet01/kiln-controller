import datetime
import json
import logging
import threading
import time

from geventwebsocket import WebSocketError
from geventwebsocket.websocket import WebSocket

from lib.oven import Oven

log = logging.getLogger(__name__)


class OvenWatcher(threading.Thread):
    _interval: float

    def __init__(self, oven: Oven, interval: float) -> None:
        self._interval = interval
        self.last_profile = None
        self.last_log = []
        self.started = None
        self.recording = False
        self.observers = []
        threading.Thread.__init__(self)
        self.daemon = True
        self.oven = oven
        self.start()

# FIXME - need to save runs of schedules in near-real-time
# FIXME - this will enable re-start in case of power outage
# FIXME - re-start also requires safety start (pausing at the beginning
# until a temp is reached)
# FIXME - re-start requires a time setting in minutes.  if power has been
# out more than N minutes, don't restart
# FIXME - this should not be done in the Watcher, but in the Oven class

    def run(self) -> None:
        while True:
            oven_state = self.oven.runtime_info
           
            # record state for any new clients that join
            if oven_state.get("state") == "RUNNING":
                self.last_log.append(oven_state)
            else:
                self.recording = False
            self.notify_all(oven_state)
            time.sleep(self._interval)
   
    def lastlog_subset(self, maxpts=50) -> list:
        """send about maxpts from lastlog by skipping unwanted data"""
        totalpts = len(self.last_log)
        if totalpts <= maxpts:
            return self.last_log
        every_nth = int(totalpts / (maxpts - 1))
        return self.last_log[::every_nth]

    def record(self, profile) -> None:
        self.last_profile = profile
        self.last_log = []
        self.started = datetime.datetime.now()
        self.recording = True
        # we just turned on, add first state for nice graph
        self.last_log.append(self.oven.runtime_info)

    def add_observer(self, observer: WebSocket) -> None:
        if self.last_profile:
            p = {
                "name": self.last_profile.name,
                "data": self.last_profile.data, 
                "type": "profile"
            }
        else:
            p = None
        
        backlog = {
            'type': "backlog",
            'profile': p,
            'log': self.lastlog_subset(),
            # 'started': self.started
        }
        backlog_json = json.dumps(backlog)
        try:
            observer.send(backlog_json)
        except WebSocketError:
            log.error("Could not send backlog to new observer")
        
        self.observers.append(observer)

    def notify_all(self, message) -> None:
        message_json = json.dumps(message)
        log.debug(f"sending to {len(self.observers)} clients: {message_json}")
        for wsock in self.observers:
            if wsock:
                try:
                    wsock.send(message_json)
                except WebSocketError:
                    log.error(f"could not write to socket {wsock}")
                    self.observers.remove(wsock)
            else:
                self.observers.remove(wsock)
