# pylint: disable=C0103

import os
import logging
import configparser

from led import LEDState


class StatusLEDConfig(configparser.ConfigParser):
    def __init__(self):
        super().__init__()

        self.parsedStates = None
        self.parsedSections = None

    def load(self, path):
        configFileContents = ""
        try:
            with open(path, "r", encoding="utf-8") as file:
                configFileContents = file.read()
                # Dump config file contents to log
                logging.info(
                    "===== Config file =====\n%s\n=======================",
                    configFileContents,
                )
        except FileNotFoundError:
            logging.error("Config file at '%s' not found.", path)
            os._exit(1)

        # Parse configuration
        self.read_string(configFileContents)

        if not "pin" in self["status_led"]:
            logging.error("Missing pin definition. Check config.")
            os._exit(1)

        self.parsedStates = [
            {"config": self[section]}
            for section in self.sections()
            if section.split(" ")[0] == "state"
        ]
        if len(self.parsedStates) == 0:
            logging.error("No states defined. Check config.")
            os._exit(1)

        for state in self.parsedStates:
            nameSplit = state["config"].name.split(" ")

            if len(nameSplit) >= 3:
                state["sectionNameList"] = nameSplit[2].split(",")
            elif len(nameSplit) <= 1:
                logging.error("Missing state name. Check config.")
                os._exit(1)

            state["stateNameList"] = nameSplit[1].split(",")

            if not "rgb" in state["config"]:
                logging.error("Missing state color. Check config.")
                os._exit(1)

            logging.info("Parsed state: %s", state["config"].name)

        self.parsedSections = [
            {"config": self[section]}
            for section in self.sections()
            if section.split(" ")[0] == "section"
        ]

        for section in self.parsedSections:
            nameSplit = section["config"].name.split(" ")

            if len(nameSplit) <= 1:
                logging.error("Missing section name. Check config.")
                os._exit(1)

            section["sectionName"] = nameSplit[1]

            logging.info("Parsed section: %s", section["config"].name)

    def getLEDStateBySection(self, currentState):
        logging.info("Loading state config of '%s'", currentState)

        states = []

        # The default section which includes all LEDs is an empty dict
        for section in [{}] + self.parsedSections:
            stateOfThisSection = None
            for state in self.parsedStates:
                if (
                    (not "sectionNameList" in state) or ("sectionName" in section)
                ) and currentState in state["stateNameList"]:

                    if (
                        "sectionNameList" in state
                        and "sectionName" in section
                        and section["sectionName"] not in state["sectionNameList"]
                    ):
                        continue

                    stateOfThisSection = state

                    if "sectionNameList" in state:
                        break

            if stateOfThisSection:
                states.append(
                    LEDState(
                        (
                            StatusLEDConfig.strToIntTuple(
                                section["config"].get("bounds")
                            )
                            if section
                            else (0, None)
                        ),
                        StatusLEDConfig.strToColor(
                            stateOfThisSection["config"].get("rgb")
                        ),
                        StatusLEDConfig.strToColor(
                            stateOfThisSection["config"].get(
                                "secondary_rgb", fallback="0, 0, 0"
                            )
                        ),
                        stateOfThisSection["config"].get("animation", fallback="solid"),
                        float(
                            stateOfThisSection["config"].get(
                                "animation_interval", fallback=1
                            )
                        ),
                    )
                )
            else:
                fallbackBounds = (0, None)
                fallbackColor = (0, 0, 0)
                if "fallback_rgb" in self["status_led"]:
                    fallbackColor = StatusLEDConfig.strToColor(
                        self.get("status_led", "fallback_rgb")
                    )
                if section:
                    if "fallback_rgb" in section["config"]:
                        fallbackBounds = StatusLEDConfig.strToIntTuple(
                            section["config"].get("bounds")
                        )
                        fallbackColor = StatusLEDConfig.strToColor(
                            section["config"].get("fallback_rgb")
                        )
                states.append(LEDState(fallbackBounds, fallbackColor))

        return states

    @staticmethod
    def strToColor(colStr):
        return tuple([int(float(val) * 255) for val in colStr.strip().split(",")])

    @staticmethod
    def strToIntTuple(tupleStr):
        return tuple([int(val) for val in tupleStr.strip().split(",")])
