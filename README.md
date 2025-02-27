# Neopixel Status LED for Klipper

A service that independently controls addressable LEDs based on Klipper status. Intended to run on a Raspberry Pi making use of its GPIOs.

## Why use this instead of the built-in LED support

Klipper to my knowledge currently has no way of processing commands while in an error state or when any MCUs are shut down. This is probably by design as a safety feature. In this state, updating LEDs connected via Klipper is not possible.

I wanted my status signal to be able to clearly show these states too if something goes wrong (Yes, having flashing lights on it is absolutely critical for printer operation). The script also adds some basic animations.

## Installation

TODO

## Configuration

TODO