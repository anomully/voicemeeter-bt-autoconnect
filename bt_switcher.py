# -*- coding: utf-8 -*-
import os
import socket
import sys
import time
from datetime import datetime

import psutil
import voicemeeterlib

# --- Config -----------------------------------------------------------------

# Output devices whose name contains this string are candidates for Hardware Out A1.
OUTPUT_MATCH = "AirPods"
# When several candidates are connected, the first name containing one of these wins.
OUTPUT_PREFERRED = ("Pro",)
# Input devices whose name contains any of these are bound to Hardware Input 1.
# Set to () to leave the input alone.
INPUT_MATCH = ("K670", "FIFINE")

POLL_INTERVAL = 3
STARTUP_DELAY = 8
LOCK_PORT = 47474
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bt_switcher_log.txt")

# ----------------------------------------------------------------------------


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


# Single instance via socket lock. A PID lock is unreliable because pythonw
# doesn't show up consistently in the process list, and a second instance
# calling restart() in a loop causes audio dropouts.
lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    lock_socket.bind(("127.0.0.1", LOCK_PORT))
except OSError:
    sys.exit(0)


def voicemeeter_running():
    return any("voicemeeter" in p.name().lower() for p in psutil.process_iter())


def get_best_output(vm):
    all_devices = [vm.device.output(i) for i in range(vm.device.outs)]
    # Windows exposes Bluetooth headphones twice: a "Headset" endpoint
    # (low-quality, with mic) and a stereo one. Only the stereo one is wanted.
    candidates = [
        d for d in all_devices
        if OUTPUT_MATCH in d["name"]
        and "Headset" not in d["name"]
        and d["type"] == "wdm"
    ]
    for d in candidates:
        if any(p in d["name"] for p in OUTPUT_PREFERRED):
            return d
    return candidates[0] if candidates else None


def get_input(vm):
    for i in range(vm.device.ins):
        d = vm.device.input(i)
        if any(m in d["name"] for m in INPUT_MATCH):
            return d
    return None


def set_output(vm, device):
    vm.set("Bus[0].device.wdm", device["name"])
    time.sleep(0.5)
    vm.command.restart()
    log(f"Set A1 to: {device['name']}")


def set_input(vm, device):
    vm.set("Strip[0].device.wdm", device["name"])
    time.sleep(0.5)
    vm.command.restart()
    log(f"Set Input 1 to: {device['name']}")


if voicemeeter_running():
    log("Started - Voicemeeter already running")
else:
    log(f"Started - waiting {STARTUP_DELAY}s for Voicemeeter")
    time.sleep(STARTUP_DELAY)

try:
    with voicemeeterlib.api("banana") as vm:
        # voicemeeterlib has no string getter for the bound device, so the
        # last-set names are tracked here instead of read back.
        last_output_name = None
        last_input_name = None

        while True:
            try:
                detected_output = get_best_output(vm)
                detected_input = get_input(vm) if INPUT_MATCH else None

                if detected_output and detected_output["name"] != last_output_name:
                    set_output(vm, detected_output)
                    last_output_name = detected_output["name"]
                elif not detected_output and last_output_name:
                    log("Output disconnected")
                    last_output_name = None

                if detected_input and detected_input["name"] != last_input_name:
                    set_input(vm, detected_input)
                    last_input_name = detected_input["name"]
                elif not detected_input and last_input_name:
                    log("Mic disconnected")
                    last_input_name = None

            except Exception as e:
                log(f"Error in loop: {e}")

            time.sleep(POLL_INTERVAL)

except Exception as e:
    log(f"Fatal error: {e}")
