# airpods-autoswitch-windows

Mac-style AirPods behaviour on Windows, for people who run their audio through Voicemeeter Banana.

Take your AirPods out of the case, put them in, and within about 3 seconds whatever you were watching or listening to is in your ears. No Bluetooth tray, no opening Voicemeeter, no re-selecting Hardware Out.

## Why this exists

My desk is a gaming and streaming setup: a studio mic, a capture card, several audio sources that need their own routing. Voicemeeter Banana is the only sane way to run all of that on Windows.

The catch is that Voicemeeter binds to a specific hardware device. When AirPods disconnect and reconnect, Voicemeeter doesn't follow them. Hardware Out A1 sits there pointing at a device that's gone, and you hear nothing until you open Voicemeeter and pick the AirPods again. Every single time.

On a Mac, AirPods just work. You put them in and the audio moves. I didn't want to choose between a real audio setup and that kind of convenience, so I wrote this. It's been running on my machine all day, every day since.

## Who it's for

- You use **Voicemeeter Banana** on Windows.
- You use **AirPods, AirPods Pro, or AirPods Max** (or any Bluetooth headphones, with one config change).
- Optionally, you have a **USB mic** that Voicemeeter loses track of when it reconnects.

If you don't use Voicemeeter, you don't need this. Windows' own default-device switching already handles plain setups.

## What it does and doesn't do

**Does:** Watches Voicemeeter's device list. When your AirPods show up, it binds them to Hardware Out A1. When your USB mic shows up, it binds it to Hardware Input 1.

**Doesn't:** Handle the Bluetooth connection. Windows does that on its own once the AirPods are paired. This fixes the part after: Voicemeeter left pointing at nothing.

## How it works

A small Python script starts at login and runs hidden in the background.

1. Every 3 seconds it asks Voicemeeter for the list of available output and input devices.
2. It looks for an output whose name contains `AirPods`, skipping the `Headset` variant (see below) and keeping only WDM devices. If more than one pair is connected, names containing `Pro` win.
3. If that device isn't the one it last bound, it sets `Bus[0]` (A1) to it and restarts the Voicemeeter audio engine so the change takes effect.
4. It does the same for the mic on `Strip[0]` (Hardware Input 1).
5. If nothing changed, it does nothing. The engine is only restarted on an actual switch.

Windows' sound settings stay pointed at Voicemeeter permanently. Only Voicemeeter's hardware bindings move.

### The AirPods "Headset" trap

Windows exposes every pair of AirPods as two devices: a stereo one, and a "Headset" one that enables the mic but drops audio to phone-call quality. If anything selects the Headset endpoint, music sounds terrible. The script ignores any device with `Headset` in its name, so you always get stereo. Use a separate mic.

## Requirements

- Windows 10 or 11
- [Voicemeeter Banana](https://vb-audio.com/Voicemeeter/banana.htm)
- Python 3.10+ with `pythonw.exe` on your PATH
- AirPods already paired in Windows Bluetooth settings

## Install

**1. Get the code and dependencies**

```powershell
git clone https://github.com/anomully/airpods-autoswitch-windows.git $HOME\airpods-autoswitch-windows
```

```powershell
pip install -r $HOME\airpods-autoswitch-windows\requirements.txt
```

**2. Set Windows sound defaults** (Settings → System → Sound → More sound settings)

- Playback tab: set **Voicemeeter Input** as Default Device and Default Communication Device.
- Recording tab: set **Voicemeeter Out B1** as Default Device and Default Communication Device.

**3. Test it**

With Voicemeeter Banana open and your AirPods connected:

```powershell
python $HOME\airpods-autoswitch-windows\bt_switcher.py
```

You should see `Set A1 to: ...AirPods...`. Take the AirPods out, put them back, and watch it rebind. `Ctrl+C` to stop.

**4. Run it at login** (PowerShell as administrator)

```powershell
schtasks /create /tn "AirPodsAutoswitch" /tr "wscript.exe $HOME\airpods-autoswitch-windows\bt_switcher.vbs" /sc ONLOGON /delay 0000:30 /rl HIGHEST /f
```

On a laptop, also let it run on battery:

```powershell
$task = Get-ScheduledTask -TaskName "AirPodsAutoswitch"; $task.Settings.DisallowStartIfOnBatteries = $false; $task.Settings.StopIfGoingOnBatteries = $false; $task | Set-ScheduledTask
```

The `.vbs` launcher exists only to start Python without a console window.

## Configuration

Edit the block at the top of [`bt_switcher.py`](bt_switcher.py):

| Setting | Default | What it does |
|---|---|---|
| `OUTPUT_MATCH` | `"AirPods"` | Substring to match your headphones' name. Change it for non-Apple headphones. |
| `OUTPUT_PREFERRED` | `("Pro",)` | Which pair wins when several are connected. |
| `INPUT_MATCH` | `("K670", "FIFINE")` | Substrings to match your USB mic. Set to `()` to leave inputs alone. |
| `POLL_INTERVAL` | `3` | Seconds between checks. |
| `STARTUP_DELAY` | `8` | Seconds to wait at login if Voicemeeter isn't running yet. |

To find your device names, open Voicemeeter's Hardware Out A1 dropdown. Names are listed exactly as the script sees them.

## Optional: USB mic reset at login

Some USB mics come up in a bad state after boot and need to be unplugged and replugged. [`reset_mic.ps1`](reset_mic.ps1) does that in software by disabling and re-enabling the device. Schedule it to run at login (administrator):

```powershell
schtasks /create /tn "ResetUSBMic" /tr "powershell.exe -ExecutionPolicy Bypass -File $HOME\airpods-autoswitch-windows\reset_mic.ps1 -Name *K670*" /sc ONLOGON /delay 0000:15 /rl HIGHEST /f
```

Replace `*K670*` with part of your mic's name as it appears in Device Manager.

## Troubleshooting

Check `bt_switcher_log.txt` next to the script first.

- **Audio drops out every few seconds.** More than one copy is running, each restarting the engine. The script guards against this with a lock on local port 47474, but make sure the scheduled task is `ONLOGON` and not a repeating trigger.
- **Music sounds like a phone call.** Something picked the AirPods Headset endpoint. Check Windows sound defaults are set to Voicemeeter, not the AirPods directly.
- **Nothing happens at login.** Run step 3 by hand to see the error. Usually `pythonw.exe` isn't on PATH; edit `bt_switcher.vbs` to use the full path to it.
- **Another app is using port 47474.** Change `LOCK_PORT` in the script.

## Notes for contributors

- `voicemeeterlib` has no string getter for the currently bound device, so the script can't read A1 back. It remembers what it last set instead. On startup it always binds once.
- The single-instance lock is a socket bind rather than a PID file because `pythonw` doesn't appear reliably in the process list.

## License

[MIT](LICENSE)
