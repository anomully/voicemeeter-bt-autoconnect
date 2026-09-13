# voicemeeter-bt-autoconnect

Makes your Bluetooth headphones just work with Voicemeeter Banana. For streamers, gamers, and anyone else running their audio through it.

Put your headphones on and your audio follows within about 3 seconds. No opening Voicemeeter, no re-selecting Hardware Out. Works with any Bluetooth headphones.

## Requirements

- Windows 10 or 11
- [Voicemeeter Banana](https://vb-audio.com/Voicemeeter/banana.htm)
- [Python 3.10+](https://www.python.org/downloads/windows/) (tick **Add python.exe to PATH** when installing)
- Headphones [paired with Windows](https://support.microsoft.com/en-us/windows/pair-a-bluetooth-device-in-windows-2be7b51f-6ae9-b757-a3b9-95ee40c3e242)

## Install

**1. Download**

[Download the ZIP](https://github.com/anomully/voicemeeter-bt-autoconnect/releases/latest/download/voicemeeter-bt-autoconnect.zip) and extract it to `C:\Users\<your name>`. Then in PowerShell:

```powershell
pip install -r $HOME\voicemeeter-bt-autoconnect\requirements.txt
```

**2. Set Windows sound defaults** (Sound settings → More sound settings)

- Playback: **Voicemeeter Input** as default and default communication device
- Recording: **Voicemeeter Out B1** as default and default communication device

**3. Start it** (PowerShell as admin)

```powershell
schtasks /create /tn "VoicemeeterBTAutoconnect" /tr "wscript.exe $HOME\voicemeeter-bt-autoconnect\bt_switcher.vbs" /sc ONLOGON /delay 0000:30 /rl HIGHEST /f; schtasks /run /tn "VoicemeeterBTAutoconnect"
```

That's it. It's running now and starts on its own every time you log in.

On a laptop, also allow it on battery:

```powershell
$task = Get-ScheduledTask -TaskName "VoicemeeterBTAutoconnect"; $task.Settings.DisallowStartIfOnBatteries = $false; $task.Settings.StopIfGoingOnBatteries = $false; $task | Set-ScheduledTask
```

## Configuration

Edit the top of [`bt_switcher.py`](bt_switcher.py). Run with `--list` to see device names as the script sees them.

| Setting | Default | What it does |
|---|---|---|
| `OUTPUT_MATCH` | `()` | Only use headphones whose name contains one of these. Empty = all. |
| `OUTPUT_EXCLUDE` | `()` | Skip names containing one of these, e.g. a Bluetooth speaker. |
| `INPUT_MATCH` | `("K670", "FIFINE")` | Your USB mic's name. `()` leaves inputs alone. |
| `POLL_INTERVAL` | `3` | Seconds between checks. |
| `STARTUP_DELAY` | `8` | Seconds to wait at login if Voicemeeter isn't running yet. |

## Optional: USB mic reset at login

If your USB mic sometimes needs replugging after boot, [`reset_mic.ps1`](reset_mic.ps1) does it in software. Schedule it (PowerShell as admin), replacing `*K670*` with part of your mic's name:

```powershell
schtasks /create /tn "ResetUSBMic" /tr "powershell.exe -ExecutionPolicy Bypass -File $HOME\voicemeeter-bt-autoconnect\reset_mic.ps1 -Name *K670*" /sc ONLOGON /delay 0000:15 /rl HIGHEST /f
```

## Troubleshooting

Start with `bt_switcher_log.txt` next to the script.

- **Audio drops out every few seconds:** more than one copy is running. Make sure the task runs at logon, not on a repeating schedule.
- **Sounds like a phone call:** Windows' sound defaults point at the headphones instead of Voicemeeter.
- **Headphones not detected:** check `--list`. Headphones using their own USB dongle aren't Windows Bluetooth devices. Otherwise, open an issue with the output.
- **Nothing happens:** run `python $HOME\voicemeeter-bt-autoconnect\bt_switcher.py` to see the error. Usually Python isn't on PATH; rerun the [Python installer](https://www.python.org/downloads/windows/), choose **Modify**, and add it.
- **Port 47474 in use:** change `LOCK_PORT` in the script.

## Why this exists

My desk is a gaming and streaming setup: studio mic, capture card, audio sources that each need their own routing. Voicemeeter is the only sane way to run that on Windows.

But Voicemeeter binds to one specific device. When Bluetooth headphones reconnect, Windows moves your audio to them and Voicemeeter doesn't. You hear nothing until you open Voicemeeter and pick them again, every time.

I didn't want to choose between a real audio setup and headphones that just work, so I wrote this. I've used it all day, every day since.

## Who it's for

- **Voicemeeter Banana** users on Windows
- with **Bluetooth headphones**
- and optionally a **USB mic** Voicemeeter loses track of on reconnect

No Voicemeeter? You don't need this. Windows already handles it.

## What it does and doesn't do

**Does:** Binds Bluetooth headphones to Hardware Out A1 when they connect. The most recently connected pair wins; if it disconnects, it falls back to any pair still connected. Also binds your USB mic to Hardware Input 1.

**Doesn't:** Connect the Bluetooth itself. Windows does that. This fixes Voicemeeter pointing at nothing afterwards.

## How it works

A hidden Python script starts at login.

1. Every 3 seconds it reads Windows' list of connected audio devices.
2. It spots Bluetooth by how the device is connected, not its name, so renamed headphones and non-English Windows work.
3. When a new pair appears, it sets A1 (`Bus[0]`) to it and restarts Voicemeeter's audio engine. Same for the mic on `Strip[0]`.
4. If nothing changed, it does nothing.

Windows' sound settings stay pointed at Voicemeeter. Only Voicemeeter's hardware bindings move.

### Lightweight by design

It runs all the time, including while you game, so it has to cost next to nothing:

- **Asleep between checks.** One check every 3 seconds.
- **About 1 ms of CPU per check** (0.04% of one core). It reads the registry instead of asking Voicemeeter, which rescans every audio device and costs ~60× more.
- **No window, tray icon, or service.** One hidden process, ~35 MB of memory.
- **No engine restarts** unless something actually connects.

Measured on my machine with Python 3.14.

### The "Headset" trap

Windows lists Bluetooth headphones twice: stereo, and a "Headset" version with the mic that sounds like a phone call. The script only ever picks stereo (Windows tags them `BTHENUM` and `BTHHFENUM`). Use a separate mic.

## Notes for contributors

- `voicemeeterlib` can't read back the bound device, so the script tracks what it last set.
- Device names come from `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio`. Voicemeeter builds its WDM names (`<description> (<interface>)`) from the same properties, so they match.
- Don't poll `vm.device.outs` / `vm.device.ins` in the loop: each call rescans hardware (~40–75 ms CPU). They're only used to confirm a device before binding.
- The single-instance lock is a socket bind because `pythonw` doesn't show reliably in the process list.

## License

[MIT](LICENSE)
