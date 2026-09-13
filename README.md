# voicemeeter-bt-autoconnect

Makes your Bluetooth headphones just work with Voicemeeter Banana, for streamers, gamers, and anyone else running their audio through it. Works with any Bluetooth headphones: AirPods, AirPods Pro, AirPods Max, Sony, Bose, Beats, anything that pairs with Windows.

Put your headphones on, and within about 3 seconds whatever you were watching or listening to is in your ears. No opening Voicemeeter, no re-selecting Hardware Out.

## Why this exists

My desk is a gaming and streaming setup: a studio mic, a capture card, several audio sources that need their own routing. Voicemeeter Banana is the only sane way to run all of that on Windows.

The catch is that Voicemeeter binds to one specific hardware device. When Bluetooth headphones disconnect and reconnect, Voicemeeter doesn't follow them. Hardware Out A1 sits there pointing at a device that's gone, and you hear nothing until you open Voicemeeter and pick your headphones again. Every single time.

Without Voicemeeter, Windows handles this fine: the headphones connect and audio moves to them. Voicemeeter breaks that. I didn't want to choose between a real audio setup and that kind of convenience, so I wrote this. It's been running on my machine all day, every day since.

## Who it's for

- You use **Voicemeeter Banana** on Windows.
- You use **Bluetooth headphones** of any brand. No config needed.
- Optionally, you have a **USB mic** that Voicemeeter loses track of when it reconnects.

If you don't use Voicemeeter, you don't need this. Windows' own default-device switching already handles plain setups. Voicemeeter is Windows-only, so this is too.

## What it does and doesn't do

**Does:** When Bluetooth headphones connect, it binds them to Voicemeeter's Hardware Out A1. If you connect a second pair, the one you just connected wins. If that pair disconnects and another is still connected, it falls back to the other one. When your USB mic shows up, it binds it to Hardware Input 1.

**Doesn't:** Handle the Bluetooth connection. Windows does that on its own once your headphones are paired. This fixes the part after: Voicemeeter left pointing at nothing.

## How it works

A small Python script starts at login and runs hidden in the background.

1. Every 3 seconds it reads Windows' list of connected audio devices and picks out the Bluetooth ones.
2. Bluetooth is detected from how Windows connects the device, not from its name. Renamed headphones, any brand, and non-English Windows all work.
3. When a Bluetooth output appears that wasn't there at the last check, it confirms Voicemeeter can see it, sets `Bus[0]` (A1) to it, and restarts the Voicemeeter audio engine so the change takes effect.
4. It does the same for the mic on `Strip[0]` (Hardware Input 1).
5. If nothing changed, it does nothing. The engine is only restarted on an actual switch.

Windows' sound settings stay pointed at Voicemeeter permanently. Only Voicemeeter's hardware bindings move.

### Lightweight by design

For this to feel seamless it has to run all the time, including while you're gaming. If you had to remember to start it, it would defeat the point. So it's built to cost next to nothing, even on a modest PC:

- **Checks every 3 seconds, not continuously.** Between checks the script is asleep and uses no CPU.
- **Each check is a quick registry read**, about 1 ms of CPU (roughly 0.04% of one core). Asking Voicemeeter for its device list makes it re-scan every audio device on the system, which costs around 60 times more, so the script only asks Voicemeeter when something has actually connected.
- **No window, no tray icon, no extra services.** One hidden Python process using about 35 MB of memory, which is mostly Python itself.
- **The audio engine only restarts when you actually connect something.** Nothing happens while your setup is stable.

Measured on the author's machine with Python 3.14. Your numbers will vary a little, but not by orders of magnitude.

### The Bluetooth "Headset" trap

Windows exposes Bluetooth headphones as two devices: a stereo one, and a "Headset" (hands-free) one that enables the headphones' mic but drops audio to phone-call quality. If anything selects the Headset endpoint, music sounds terrible. Windows tags the two differently (`BTHENUM` for stereo, `BTHHFENUM` for hands-free), and the script only ever picks stereo. Use a separate mic.

## Requirements

- Windows 10 or 11
- [Voicemeeter Banana](https://vb-audio.com/Voicemeeter/banana.htm)
- [Python 3.10 or newer](https://www.python.org/downloads/windows/). In the installer, tick **Add python.exe to PATH** before clicking Install.
- Headphones already [paired with Windows](https://support.microsoft.com/en-us/windows/pair-a-bluetooth-device-in-windows-2be7b51f-6ae9-b757-a3b9-95ee40c3e242)

## Install

The commands below go in PowerShell. To open it, right-click the Start button and choose **Terminal** (or **Windows PowerShell**).

**1. Download it**

[Download the ZIP](https://github.com/anomully/voicemeeter-bt-autoconnect/archive/refs/heads/main.zip) and extract it into your user folder (`C:\Users\<your name>`). Rename the extracted folder to `voicemeeter-bt-autoconnect`.

If you use [Git](https://git-scm.com/downloads/win), you can clone it instead:

```powershell
git clone https://github.com/anomully/voicemeeter-bt-autoconnect.git $HOME\voicemeeter-bt-autoconnect
```

**Install the two Python packages it needs:**

```powershell
pip install -r $HOME\voicemeeter-bt-autoconnect\requirements.txt
```

**2. Set Windows sound defaults** (Settings → System → Sound → More sound settings)

- Playback tab: set **Voicemeeter Input** as Default Device and Default Communication Device.
- Recording tab: set **Voicemeeter Out B1** as Default Device and Default Communication Device.

**3. Test it**

With Voicemeeter Banana open and your headphones connected, see what it detects (read-only, changes nothing):

```powershell
python $HOME\voicemeeter-bt-autoconnect\bt_switcher.py --list
```

Then run it for real:

```powershell
python $HOME\voicemeeter-bt-autoconnect\bt_switcher.py
```

You should see `Set A1 to: Headphones (...)`. Disconnect the headphones, reconnect them, and watch it rebind. `Ctrl+C` to stop.

**4. Run it at login** (PowerShell as administrator)

```powershell
schtasks /create /tn "VoicemeeterBTAutoconnect" /tr "wscript.exe $HOME\voicemeeter-bt-autoconnect\bt_switcher.vbs" /sc ONLOGON /delay 0000:30 /rl HIGHEST /f
```

On a laptop, also let it run on battery:

```powershell
$task = Get-ScheduledTask -TaskName "VoicemeeterBTAutoconnect"; $task.Settings.DisallowStartIfOnBatteries = $false; $task.Settings.StopIfGoingOnBatteries = $false; $task | Set-ScheduledTask
```

The `.vbs` launcher exists only to start Python without a console window.

## Configuration

Edit the block at the top of [`bt_switcher.py`](bt_switcher.py):

| Setting | Default | What it does |
|---|---|---|
| `OUTPUT_MATCH` | `()` | Only use Bluetooth outputs whose name contains one of these. Empty means all. |
| `OUTPUT_EXCLUDE` | `()` | Skip Bluetooth outputs whose name contains one of these, e.g. `("SRS-XB10",)` to ignore a speaker. |
| `INPUT_MATCH` | `("K670", "FIFINE")` | Substrings to match your USB mic. Set to `()` to leave inputs alone. |
| `POLL_INTERVAL` | `3` | Seconds between checks. |
| `STARTUP_DELAY` | `8` | Seconds to wait at login if Voicemeeter isn't running yet. |

To see device names exactly as the script sees them, run it with `--list`.

## Optional: USB mic reset at login

Some USB mics come up in a bad state after boot and need to be unplugged and replugged. [`reset_mic.ps1`](reset_mic.ps1) does that in software by disabling and re-enabling the device. Schedule it to run at login (administrator):

```powershell
schtasks /create /tn "ResetUSBMic" /tr "powershell.exe -ExecutionPolicy Bypass -File $HOME\voicemeeter-bt-autoconnect\reset_mic.ps1 -Name *K670*" /sc ONLOGON /delay 0000:15 /rl HIGHEST /f
```

Replace `*K670*` with part of your mic's name as it appears in Device Manager.

## Troubleshooting

Check `bt_switcher_log.txt` next to the script first.

- **Audio drops out every few seconds.** More than one copy is running, each restarting the engine. The script guards against this with a lock on local port 47474, but make sure the scheduled task is `ONLOGON` and not a repeating trigger.
- **Music sounds like a phone call.** Something picked the headphones' Headset endpoint. Check Windows sound defaults are set to Voicemeeter, not the headphones directly.
- **Your headphones aren't detected.** Run with `--list`. Headphones that use their own USB dongle aren't Windows Bluetooth devices, so they won't show up. Open an issue with the output.
- **Nothing happens at login.** Run step 3 by hand to see the error. Usually Python isn't on PATH: re-run the [Python installer](https://www.python.org/downloads/windows/), choose **Modify**, and tick **Add Python to environment variables**.
- **Another app is using port 47474.** Change `LOCK_PORT` in the script.

## Notes for contributors

- `voicemeeterlib` has no string getter for the currently bound device, so the script can't read A1 back. It remembers what it last set instead. On startup it always binds once.
- Detection reads endpoint properties from `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render` and `\Capture`, so there are no extra dependencies. Voicemeeter's WDM names are `<device description> (<interface name>)`, built from the same properties, so the two line up exactly.
- Don't poll `vm.device.outs` / `vm.device.ins` in the loop. Each call makes Voicemeeter re-enumerate hardware (~40 ms and ~75 ms of CPU on the author's machine, versus ~1 ms for the registry scan). The script only calls them to confirm Voicemeeter can see a device right before binding it.
- The single-instance lock is a socket bind rather than a PID file because `pythonw` doesn't appear reliably in the process list.

## License

[MIT](LICENSE)
