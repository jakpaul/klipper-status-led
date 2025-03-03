# pylint: disable=C0103

import sys
import os
import argparse
import logging
import socket
import time
import errno
import select
import json

from log import log
from config import StatusLEDConfig
from config import InvalidConfigException
from led import AnimatedLED

CONFIG_PATH_DEFAULT = os.path.expanduser("~/printer_data/config/status_led.cfg")
SOCKET_PATH_DEFAULT = os.path.expanduser("~/printer_data/comms/klippy.sock")
LOG_PATH_DEFAULT = os.path.expanduser("~/printer_data/logs/status_led.log")
POLLING_INTERVAL_S = 0.25
MAX_NUM_REQUESTS_IN_BUFFER = 5

argParser = argparse.ArgumentParser(
    prog="Klipper Status LED script",
    description="Monitor Klipper status via its socket API and control a neopixel LED on Raspberry Pi GPIO",
)
argParser.add_argument("-c", "--config", default=CONFIG_PATH_DEFAULT)
argParser.add_argument("-s", "--socket", default=SOCKET_PATH_DEFAULT)
argParser.add_argument("-l", "--log", default=LOG_PATH_DEFAULT)
argParser.add_argument("-v", "--verbose", action="store_true", default=False)


def createSocket(socketPath):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.setblocking(0)
    logging.info("Waiting for connection to '%s'", socketPath)

    while True:
        try:
            sock.connect(socketPath)
        except OSError as e:
            if e.errno == errno.ECONNREFUSED:
                time.sleep(0.1)
                continue
            elif e.errno == errno.ENOENT:
                # No such file or directory
                logging.error(
                    "Unable to open socket at '%s': No such file or directory. "
                    "Check your config or the --socket option.",
                    socketPath,
                )
            else:
                logging.error(
                    "Unable to open socket at '%s' [%d, %s]\n",
                    socketPath,
                    e.errno,
                    errno.errorcode[e.errno],
                )

            log.flushAndExit(e.errno)
        break

    logging.info("Connected.")
    return sock


class StatusMonitor:
    def __init__(self, config, socketPathFallback):
        self.config = config

        self.sock = None
        self.poll = None

        self.socketPath = config.get(
            "status_led", "klippy_uds_path", fallback=socketPathFallback
        )
        self.carriedData = b""

        self.isConnected = False
        
        # possible states: "ready", "startup", "error", "shutdown"
        self.lastKlipperState = (
            ""
        )
        # possible states: "standby", "printing", "paused", "cancelled", "error", "complete"
        self.lastPrintState = ""
        self.lastGcodeState = ""

        self.ledState = None

        self.led = AnimatedLED(config)
        self.updateLEDState()

    def connect(self):
        self.sock = createSocket(self.socketPath)

        if self.sock:
            self.isConnected = True

            self.poll = select.poll()
            self.poll.register(self.sock, select.POLLIN | select.POLLHUP)

    def registerRemoteMethods(self):
        ledStateMethodCmd = '{"id": "ksl-set-state-reg", "method": "register_remote_method", "params": {"response_template": {"action": "set_status_led"}, "remote_method": "set_status_led"}}'

        self.sendRequest(ledStateMethodCmd)

    def queryStatus(self):
        infoCmd = '{"id": "ksl-info", "method": "info", "params": {}}'
        statsCmd = '{"id": "ksl-stats", "method": "objects/query", "params": {"objects": {"print_stats": ["state"]}}}'

        self.sendRequest(infoCmd)
        if self.lastKlipperState == "ready":
            self.sendRequest(statsCmd)

    def sendRequest(self, jsonStr):
        try:
            return self.sock.send(jsonStr.encode() + b"\x03")
        except BrokenPipeError:
            logging.warning("Broken pipe.")
            self.isConnected = False

            self.updateLEDState()

    def updateStatusFromSocket(self, parsed):
        stateHasChanged = False

        if (
            "action" in parsed
            and "params" in parsed
            and parsed["action"] == "set_status_led"
        ):
            if "state" in parsed["params"]:
                newState = parsed["params"]["state"]

                if self.lastGcodeState != newState:
                    self.lastGcodeState = newState
                    stateHasChanged = True
                    logging.debug(
                        "Gcode state: %s",
                        self.lastGcodeState if self.lastGcodeState else "[None]",
                    )

            elif "enabled" in parsed["params"]:
                logging.debug("se: %s", bool(parsed["params"]["enabled"]))
                self.led.setEnabled(bool(parsed["params"]["enabled"]))

        elif "id" in parsed:
            if parsed["id"] == "ksl-set-state-reg":
                logging.info("Remote method 'set_status_led' registered.")

            elif parsed["id"] == "ksl-info":
                newState = parsed["result"]["state"]

                if self.lastKlipperState != newState:
                    self.lastKlipperState = newState
                    self.lastGcodeState = ""
                    stateHasChanged = True
                    logging.debug("Klipper state: %s", self.lastKlipperState)

            elif parsed["id"] == "ksl-stats":
                newState = parsed["result"]["status"]["print_stats"]["state"]

                if self.lastPrintState != newState:
                    self.lastPrintState = newState
                    self.lastGcodeState = ""
                    stateHasChanged = True
                    logging.debug("Print state: %s", self.lastPrintState)

        if stateHasChanged:
            self.updateLEDState()

    def updateLEDState(self):
        stateStr = "unknown"
        if self.isConnected:
            if self.lastGcodeState != "":
                stateStr = "gcode_" + self.lastGcodeState
            elif self.lastKlipperState == "ready" and self.lastPrintState != "":
                stateStr = "print_" + self.lastPrintState
            else:
                stateStr = "klipper_" + self.lastKlipperState

        self.led.updateState(self.config.getLEDStateBySection(stateStr))

    def processFromSocket(self):
        data = None
        try:
            data = self.sock.recv(4096)
        except Exception as e:  # pylint: disable=W0718
            logging.warning("Error reading from socket:\n%s\n", e)

        if not data:
            logging.warning("Socket closed.")
            self.isConnected = False
            return

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
        requestsInBuffer = 0

        while True:
            if not self.isConnected:
                self.connect()

                if self.isConnected:
                    self.registerRemoteMethods()

                nextTime = time.time()
                requestsInBuffer = 0
            else:
                res = self.poll.poll(1000.0)
                for _ in res:
                    self.processFromSocket()
                    requestsInBuffer = requestsInBuffer - 1

                # Stop sending when Klipper is unresponsive
                # to prevent overloading
                # When there are too many pending requests,
                # Klipper may be unable to handle them
                if requestsInBuffer < MAX_NUM_REQUESTS_IN_BUFFER:
                    self.queryStatus()

                    requestsInBuffer = requestsInBuffer + 1

                nextTime = max(nextTime + POLLING_INTERVAL_S, time.time())
                time.sleep(max(0, nextTime - time.time()))


def main():
    args = argParser.parse_args()

    log.initQueue(args.verbose)

    logging.info("Startup")

    config = StatusLEDConfig()
    logPath = config.get("status_led", "log_path", fallback=args.log)

    try:
        config.load(args.config)

        log.start(logPath)

        monitor = StatusMonitor(config, args.socket)
        monitor.run()
    except InvalidConfigException:
        log.start(logPath)
        log.flushAndExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # pylint: disable=W0718
        logging.exception("Fatal error in main:\n%s\n", e)
        log.flushAndExit(1)
