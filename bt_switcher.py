# -*- coding: utf-8 -*-
import os
import socket
import sys
import time
import winreg
from datetime import datetime

import psutil
import voicemeeterlib

# --- Config -----------------------------------------------------------------

# Any Bluetooth headphones are bound to Hardware Out A1. Optionally narrow that:
# only names containing one of OUTPUT_MATCH are used (empty = all), and names
# containing one of OUTPUT_EXCLUDE are skipped (e.g. a Bluetooth speaker).
OUTPUT_MATCH = ()
OUTPUT_EXCLUDE = ()
# Input devices whose name contains any of these are bound to Hardware Input 1.
# Set to () to leave the input alone.
INPUT_MATCH = ("K670", "FIFINE")

POLL_INTERVAL = 3
STARTUP_DELAY = 8
LOCK_PORT = 47474
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bt_switcher_log.txt")

# ----------------------------------------------------------------------------

RENDER_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
PKEY_DEVICE_DESC = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
PKEY_ENUMERATOR = "{a45c254e-df1c-4efd-8020-67d146a850e0},24"
PKEY_INTERFACE_NAME = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
DEVICE_STATE_ACTIVE = 1


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def voicemeeter_running():
    return any("voicemeeter" in p.name().lower() for p in psutil.process_iter())


def bluetooth_stereo_outputs():
    """Names of active Bluetooth stereo outputs, formatted the way Voicemeeter lists them.

    Windows exposes Bluetooth headphones twice: a stereo endpoint (enumerator
    BTHENUM) and a low-quality hands-free "Headset" endpoint (BTHHFENUM). Only
    the stereo one is wanted. The enumerator is used instead of the device name
    because names are user-renamable and localized.
    """
    names = set()
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, RENDER_KEY) as render:
        for i in range(winreg.QueryInfoKey(render)[0]):
            endpoint_id = winreg.EnumKey(render, i)
            try:
                with winreg.OpenKey(render, endpoint_id) as endpoint:
                    if winreg.QueryValueEx(endpoint, "DeviceState")[0] != DEVICE_STATE_ACTIVE:
                        continue
                    with winreg.OpenKey(endpoint, "Properties") as props:
                        if winreg.QueryValueEx(props, PKEY_ENUMERATOR)[0] != "BTHENUM":
                            continue
                        desc = winreg.QueryValueEx(props, PKEY_DEVICE_DESC)[0]
                        interface = winreg.QueryValueEx(props, PKEY_INTERFACE_NAME)[0]
            except OSError:
                continue
            names.add(f"{desc} ({interface})")
    return names


def get_output_candidates(vm):
    bluetooth = bluetooth_stereo_outputs()
    candidates = []
    for i in range(vm.device.outs):
        d = vm.device.output(i)
        if d["type"] != "wdm" or d["name"] not in bluetooth:
            continue
        if OUTPUT_MATCH and not any(m in d["name"] for m in OUTPUT_MATCH):
            continue
        if any(x in d["name"] for x in OUTPUT_EXCLUDE):
            continue
        candidates.append(d["name"])
    return candidates


def pick_output(candidates, previous_candidates, current):
    # Like a Mac, the headphones you just connected win.
    newly_connected = [n for n in candidates if n not in previous_candidates]
    if newly_connected:
        return newly_connected[-1]
    if current not in candidates and candidates:
        return candidates[0]
    return None


def get_input(vm):
    for i in range(vm.device.ins):
        d = vm.device.input(i)
        if any(m in d["name"] for m in INPUT_MATCH):
            return d
    return None


def set_output(vm, name):
    vm.set("Bus[0].device.wdm", name)
    time.sleep(0.5)
    vm.command.restart()
    log(f"Set A1 to: {name}")


def set_input(vm, device):
    vm.set("Strip[0].device.wdm", device["name"])
    time.sleep(0.5)
    vm.command.restart()
    log(f"Set Input 1 to: {device['name']}")


def print_detected_devices():
    with voicemeeterlib.api("banana") as vm:
        print("A1 candidates (Bluetooth headphones):")
        for name in get_output_candidates(vm) or ["none"]:
            print(f"  {name}")
        mic = get_input(vm) if INPUT_MATCH else None
        print("Input 1 candidate:")
        print(f"  {mic['name'] if mic else 'none'}")


# Read-only, so it skips the lock and can run alongside the background copy.
if "--list" in sys.argv:
    print_detected_devices()
    sys.exit(0)

# Single instance via socket lock. A PID lock is unreliable because pythonw
# doesn't show up consistently in the process list, and a second instance
# calling restart() in a loop causes audio dropouts.
lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    lock_socket.bind(("127.0.0.1", LOCK_PORT))
except OSError:
    sys.exit(0)

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
        last_candidates = []
        last_input_name = None

        while True:
            try:
                candidates = get_output_candidates(vm)
                detected_input = get_input(vm) if INPUT_MATCH else None

                target = pick_output(candidates, last_candidates, last_output_name)
                if target and target != last_output_name:
                    set_output(vm, target)
                    last_output_name = target
                elif not candidates and last_output_name:
                    log("Output disconnected")
                    last_output_name = None
                last_candidates = candidates

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
