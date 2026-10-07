# Bluey for Windows

Windows 10/11 desktop host for either the Android or existing iPhone companion. Python 3.11+ with Tcl/Tk is required; the python.org installer includes it by default. No Xcode, Swift, or paid automation service is needed.

In PowerShell, from this directory:

```powershell
.\run.ps1
```

Alternatively create a virtual environment, install `requirements.txt`, and run `python -m bluey.app`. The app opens a control window and a transparent, click-through blueberry cursor. Choose **OpenAI key…** to save your key in Windows Credential Manager. The key is never written to this repository or sent to the phone; the phone receives a ten-minute Realtime token.

Click **Start pairing**, allow Python through Windows Firewall on **Private networks only**, and put both devices on the same trusted Wi-Fi. Bluey advertises `_googly._tcp` over mDNS and shows its IPv4 addresses and TCP port. If discovery fails, enter one of those addresses and the displayed port in the Android pairing panel. Never forward this port on your router.

Like the existing Mac transport, pairing is unencrypted and unauthenticated. Other devices on that network can request screen captures, short-lived AI tokens, and action confirmations. Only start sharing on a network whose devices you trust. **Stop pairing** closes connections and turns computer control off. The primary display is used for screen images and coordinates.

Double tap the phone to start or end voice. Hold to ask; release to request a reply. Text appears by the Windows cursor and on Android. Move the real pointer and the phone's eyes follow it. `look_at_screen` captures the primary display, and `point_at_spot` points on the same 0–1000 grid. The host supports text, screenshots, and tool replies with the existing Swift packet format, so an iPhone can pair too.

## Computer control

[PyAutoGUI](https://github.com/asweigart/pyautogui) provides mouse and keyboard input. It has approximately 12,700 GitHub stars as inspected during implementation. [pywinauto](https://github.com/pywinauto/pywinauto) provides the Windows UI Automation password-field check.

Check **Let Bluey use the computer**, then restart the phone's voice session to expose the action tools. Each click, drag, scroll, shortcut, text entry, app launch, or URL open requires a local Windows **Allow** click within 30 seconds. The prompt shows the exact requested arguments, restores the original foreground window, and cancels if focus restoration fails. The controller rechecks that it is enabled immediately before acting.

Press **Ctrl+Alt+S**, uncheck the control switch, stop pairing, or move the mouse to a primary-screen corner to stop. PyAutoGUI's failsafe remains enabled. Text entry checks cancellation between characters. Keyboard input is refused if Windows UI Automation reports a password field or cannot establish the field's status. Do not approve entry of passwords, codes, or payment details into ordinary text fields either. The model's instructions also prohibit that behavior.

This first Windows version supports printable ASCII text, common shortcuts, primary-display coordinates, and an app allowlist (Notepad, Calculator, Paint). It does not support administrator/elevated application control, OCR target IDs (`point_at`), arbitrary shell execution, meeting-note audio transcription, or the Mac report panel. PyAutoGUI cannot reliably control protected Windows desktops. A denied action reports failure to the model; it is never described as completed.

## Checks and packaging

```powershell
python -m unittest discover -s tests -v
python -m pip install pyinstaller==6.15.0
python -m PyInstaller --noconfirm --windowed --onedir --name Bluey --paths . --collect-submodules keyring.backends --collect-submodules pywinauto --hidden-import comtypes --hidden-import pyautogui launcher.py
```

The output is `dist/Bluey/Bluey.exe`; distribute the complete `dist/Bluey` directory. The Windows CI job builds this directory as an artifact. Windows runtime validation still needs actual Windows and a paired phone. The protocol, host dispatch, and automation-policy tests can run on Linux without a desktop by injecting screen/input adapters.
