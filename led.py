# pylint: disable=C0103

import os
import logging
import math

import board
import neopixel

import time, threading

# ugly pin lookup dictionary
PIN_DICT = {
    "D0": board.D0,
    "D1": board.D1,
    "D2": board.D2,
    "D3": board.D3,
    "D4": board.D4,
    "D5": board.D5,
    "D6": board.D6,
    "D7": board.D7,
    "D8": board.D8,
    "D9": board.D9,
    "D10": board.D10,
    "D11": board.D11,
    "D12": board.D12,
    "D13": board.D13,
    "D14": board.D14,
    "D15": board.D15,
    "D16": board.D16,
    "D17": board.D17,
    "D18": board.D18,
    "D19": board.D19,
    "D20": board.D20,
    "D21": board.D21,
    "D22": board.D22,
    "D23": board.D23,
    "D24": board.D24,
    "D25": board.D25,
    "D26": board.D26,
    "D27": board.D27,
}

ANIM_FUNCTIONS = {
    "solid": lambda t: (1.0, 0.0),
    "blink": lambda t: (0.0 if periodic(t) <= 0.5 else 1.0, 0.0),
    "alternate": lambda t: (
        0.0 if periodic(t) <= 0.5 else 1.0,
        0.0 if periodic(t) > 0.5 else 1.0,
    ),
    "ease": lambda t: (math.sin(periodic(t) * math.pi) ** 2, 0.0),
    "ease-alternate": lambda t: (
        math.sin(periodic(t) * math.pi) ** 2,
        math.cos(periodic(t) * math.pi) ** 2,
    ),
}

ANIMATE_STEP_S = 0.01


def periodic(t):
    # assume t > 0
    return t - int(t)


class AnimatedLED:
    def __init__(self, config):
        self.config = config

        self.states = None
        self.brightnesses = None

        try:
            self.leds = neopixel.NeoPixel(
                PIN_DICT[config.get("status_led", "pin")],
                int(config.get("status_led", "chain_count", fallback="1")),
                auto_write=False,
            )
            self.leds.fill((0, 0, 0))
            self.leds.show()

        except Exception as e:  # pylint: disable=W0718
            logging.exception(
                "Error initializing neopixels:\n%s\n",
                e,
            )
            os._exit(1)

        timerThread = threading.Thread(target=self.run)
        timerThread.start()

    def updateState(self, states):
        self.states = states
        self.write(True)

    def write(self, forceUpdate):
        if not self.states or not self.leds:
            return

        brightnesses = []

        for sectionState in self.states:
            currentBrightness = ANIM_FUNCTIONS[sectionState.anim](
                time.time() / sectionState.animInterval
            )
            brightnesses.append(currentBrightness)

            sectionLen = (
                (sectionState.bounds[1] - sectionState.bounds[0])
                if sectionState.bounds[1] is not None
                else len(self.leds)
            )
            mixedColor = [
                (prim * currentBrightness[0] + sec * currentBrightness[1])
                for prim, sec in zip(sectionState.rgb, sectionState.secondaryRgb)
            ]
            self.leds[sectionState.bounds[0] : sectionState.bounds[1]] = [
                mixedColor
            ] * sectionLen

        # To avoid updating when the animation state is still the same,
        # check whether brightnesses have changed
        if (
            not forceUpdate
            and self.brightnesses is not None
            and all([b[0] == b[1] for b in zip(brightnesses, self.brightnesses)])
        ):
            return

        self.brightnesses = brightnesses

        self.leds.show()

    def run(self):
        nextTime = time.time()
        while True:
            self.write(False)

            nextTime = nextTime + ANIMATE_STEP_S
            time.sleep(max(0, nextTime - time.time()))


class LEDState:
    def __init__(
        self,
        bounds=(0, None),
        rgb=(0, 0, 0),
        secondaryRgb=(0, 0, 0),
        anim="solid",
        animInterval=1,
        sectionName="default",
    ):
        self.bounds = bounds
        self.rgb = rgb
        self.secondaryRgb = secondaryRgb
        self.anim = anim
        self.animInterval = animInterval

        logging.info(
            "Section ('%s' | %s) state: \t %s | %s | %s | %ss",
            sectionName,
            bounds,
            rgb,
            secondaryRgb,
            anim,
            animInterval,
        )
