# pylint: disable=C0103

import os
import sys

import logging
import logging.handlers

from queue import SimpleQueue as Queue


class Log:
    def __init__(self):
        self.queue = None
        self.listener = None

    def initQueue(self, isVerbose):
        rootLogger = logging.getLogger()

        self.queue = Queue()
        queueHandler = logging.handlers.QueueHandler(self.queue)
        rootLogger.addHandler(queueHandler)
        rootLogger.setLevel(logging.DEBUG if isVerbose else logging.INFO)

    def start(self, logFilePath=None):
        print(f"Init log: {logFilePath}")
        formatter = logging.Formatter(
            "%(asctime)s [%(filename)s:%(funcName)s()] [%(levelname)s] - %(message)s"
        )

        stdOutHandler = logging.StreamHandler(sys.stdout)
        stdOutHandler.setFormatter(formatter)
        fileHandler = None

        try:
            fileHandler = logging.handlers.RotatingFileHandler(
                logFilePath, maxBytes=4194304, backupCount=1
            )
            fileHandler.setFormatter(formatter)
            self.listener = logging.handlers.QueueListener(
                self.queue, fileHandler, stdOutHandler
            )
        except Exception as e:  # pylint: disable=W0718
            logging.error("Failed to initialize file logging:\n%s\n", e)
            fileHandler = None

        if not fileHandler or not logFilePath:
            logging.warning("File logs are disabled. Logging to stdout only.")
            self.listener = logging.handlers.QueueListener(
                self.queue, stdOutHandler
            )

        self.listener.start()

    def flush(self):
        self.listener.stop()

    def flushAndExit(self, code):
        self.flush()
        os._exit(code)


log = Log()
