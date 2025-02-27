# pylint: disable=C0103

import sys
import os
import logging
import traceback
import socket
import time
import errno
import select
import json

from config import StatusLEDConfig
from led import AnimatedLED

SOCKET_PATH_DEFAULT = "/home/paulg/printer_data/comms/klippy.sock"
POLLING_INTERVAL_S = 0.25

logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


def createSocket(socketPath):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.setblocking(0)
    logging.info("Waiting for connect to %s\n", socketPath)

    while True:
        try:
            sock.connect(socketPath)
        except socket.error as e:
            if e.errno == errno.ECONNREFUSED:
                time.sleep(0.1)
                continue

            logging.error(
                "Unable to connect socket %s [%d,%s]\n",
                socketPath, e.errno, errno.errorcode[e.errno]
            )

            return None
        break

    logging.info("Connection.\n")
    return sock


class StatusMonitor:
    def __init__(self, config):
        self.config = config

        self.socketPath = config.get(
            "status_led", "socketPath", fallback=SOCKET_PATH_DEFAULT
        )
        self.carriedData = b""

        self.isConnected = False
        self.lastKlipperState = (
            ""  # possible states: "ready", "startup", "error", "shutdown"
        )
        self.lastPrintState = (
            ""  # possible states: "standby", "printing", "paused", "error", "complete"
        )
        self.lastCustomState = ""

        self.ledState = None

        self.led = AnimatedLED(config)
        self.updateLEDState()

    def connect(self):
        self.sock = createSocket(self.socketPath)

        if self.sock:
            self.isConnected = True

            self.poll = select.poll()
            self.poll.register(self.sock, select.POLLIN | select.POLLHUP)

    def queryStatus(self):
        # cmd = '{"id": "ksl-info", "method": "info", "params": {}}'
        # cmd = '{"id": "ksl-info", "method": "objects/query", "params": {"objects": {"status": ["progress"], "print_stats": ["state"]}}}'
        infoCmd = '{"id": "ksl-info", "method": "info", "params": {}}'
        statsCmd = '{"id": "ksl-stats", "method": "objects/query", "params": {"objects": {"print_stats": ["state"]}}}'

        def sendFunc(m, jsonStr):
            return m.sock.send(jsonStr.encode() + b"\x03")

        try:
            sendFunc(self, infoCmd)
            if self.lastKlipperState == "ready":
                sendFunc(self, statsCmd)
        except BrokenPipeError:
            logging.warning("Broken pipe.")
            self.isConnected = False

            self.updateLEDState()

    def updateStatusFromSocket(self, parsed):
        stateHasChanged = False

        if parsed["id"] == "ksl-info":
            newState = parsed["result"]["state"]
            if self.lastKlipperState != newState:
                self.lastKlipperState = newState
                stateHasChanged = True
                logging.info("Klipper state: %s", self.lastKlipperState)

        elif parsed["id"] == "ksl-stats":
            newState = parsed["result"]["status"]["print_stats"]["state"]
            if self.lastPrintState != newState:
                self.lastPrintState = newState
                stateHasChanged = True
                logging.info("Print state: %s", self.lastPrintState)

        if stateHasChanged:
            # Clear the custom state
            self.lastCustomState = ""

            self.updateLEDState()

    def updateLEDState(self):
        stateStr = "unknown"
        if self.isConnected:
            if self.lastCustomState != "":
                stateStr = "custom_" + self.lastCustomState
            elif self.lastKlipperState == "ready" and self.lastPrintState != "":
                stateStr = "print_" + self.lastPrintState
            else:
                stateStr = "klipper_" + self.lastKlipperState

        self.led.updateState(self.config.getLEDStateBySection(stateStr))

    def processFromSocket(self):
        data = self.sock.recv(4096)
        if not data:
            sys.stderr.write("Socket closed\n")
            sys.exit(0)

        # logging.info("recv")

        parts = data.split(b"\x03")
        parts[0] = self.carriedData + parts[0]
        self.carriedData = parts.pop()

        for line in parts:
            self.handleMessage(line)

    def handleMessage(self, line):
        parsed = json.loads(line.decode())
        # logging.info(f"GOT: {parsed}")
        self.updateStatusFromSocket(parsed)

    def run(self):
        nextTime = time.time()
        while True:
            if not self.isConnected:
                self.connect()
            else:
                res = self.poll.poll(1000.0)
                for _ in res:
                    self.processFromSocket()

                self.queryStatus()

                nextTime = nextTime + POLLING_INTERVAL_S
                time.sleep(max(0, nextTime - time.time()))


def main():
    config = StatusLEDConfig()
    config.load()

    logging.info("Startup")

    monitor = StatusMonitor(config)
    monitor.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # pylint: disable=W0718
        logging.exception("Fatal error in main:\n%s\n", e)
        os._exit(1)
