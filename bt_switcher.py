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

MMDEVICES_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio"
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


def active_endpoints(flow):
    """{name: enumerator} for active Windows audio endpoints ("Render" or "Capture").

    Names are formatted the way Voicemeeter lists WDM devices. This is read
    from the registry on every poll because it costs about 1 ms of CPU, while
    asking Voicemeeter for its device list makes it re-scan every audio device
    (tens of ms each time).
    """
    endpoints = {}
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"{MMDEVICES_KEY}\{flow}") as root:
        for i in range(winreg.QueryInfoKey(root)[0]):
            endpoint_id = winreg.EnumKey(root, i)
            try:
                with winreg.OpenKey(root, endpoint_id) as endpoint:
                    if winreg.QueryValueEx(endpoint, "DeviceState")[0] != DEVICE_STATE_ACTIVE:
                        continue
                    with winreg.OpenKey(endpoint, "Properties") as props:
                        enumerator = winreg.QueryValueEx(props, PKEY_ENUMERATOR)[0]
                        desc = winreg.QueryValueEx(props, PKEY_DEVICE_DESC)[0]
                        interface = winreg.QueryValueEx(props, PKEY_INTERFACE_NAME)[0]
            except OSError:
                continue
            endpoints[f"{desc} ({interface})"] = enumerator
    return endpoints


def get_output_candidates():
    # Windows exposes Bluetooth headphones twice: a stereo endpoint (BTHENUM)
    # and a low-quality hands-free "Headset" endpoint (BTHHFENUM). Only stereo
    # is wanted. The enumerator is used instead of the name because names are
    # user-renamable and localized.
    candidates = []
    for name, enumerator in active_endpoints("Render").items():
        if enumerator != "BTHENUM":
            continue
        if OUTPUT_MATCH and not any(m in name for m in OUTPUT_MATCH):
            continue
        if any(x in name for x in OUTPUT_EXCLUDE):
            continue
        candidates.append(name)
    return sorted(candidates)


def get_input_candidate():
    if not INPUT_MATCH:
        return None
    for name in sorted(active_endpoints("Capture")):
        if any(m in name for m in INPUT_MATCH):
            return name
    return None


def pick_output(candidates, previous_candidates, current):
    # The headphones you just connected win.
    newly_connected = [n for n in candidates if n not in previous_candidates]
    if newly_connected:
        return newly_connected[-1]
    if current not in candidates and candidates:
        return candidates[0]
    return None


def voicemeeter_has(vm, direction, name):
    # Windows can list a device a moment before Voicemeeter picks it up.
    # Binding a name Voicemeeter doesn't know yet does nothing, so check first.
    if direction == "out":
        devices = (vm.device.output(i) for i in range(vm.device.outs))
    else:
        devices = (vm.device.input(i) for i in range(vm.device.ins))
    return any(d["type"] == "wdm" and d["name"] == name for d in devices)


def set_output(vm, name):
    vm.set("Bus[0].device.wdm", name)
    time.sleep(0.5)
    vm.command.restart()
    log(f"Set A1 to: {name}")


def set_input(vm, name):
    vm.set("Strip[0].device.wdm", name)
    time.sleep(0.5)
    vm.command.restart()
    log(f"Set Input 1 to: {name}")


def print_detected_devices():
    print("A1 candidates (Bluetooth headphones):")
    for name in get_output_candidates() or ["none"]:
        print(f"  {name}")
    print("Input 1 candidate:")
    print(f"  {get_input_candidate() or 'none'}")


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
                candidates = get_output_candidates()
                target = pick_output(candidates, last_candidates, last_output_name)
                if target and target != last_output_name:
                    # If Voicemeeter hasn't seen it yet, leave state alone so
                    # the next poll retries.
                    if voicemeeter_has(vm, "out", target):
                        set_output(vm, target)
                        last_output_name = target
                        last_candidates = candidates
                else:
                    if not candidates and last_output_name:
                        log("Output disconnected")
                        last_output_name = None
                    last_candidates = candidates

                detected_input = get_input_candidate()
                if detected_input and detected_input != last_input_name:
                    if voicemeeter_has(vm, "in", detected_input):
                        set_input(vm, detected_input)
                        last_input_name = detected_input
                elif not detected_input and last_input_name:
                    log("Mic disconnected")
                    last_input_name = None

            except Exception as e:
                log(f"Error in loop: {e}")

            time.sleep(POLL_INTERVAL)

except Exception as e:
    log(f"Fatal error: {e}")
