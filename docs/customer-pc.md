# Bluey on a customer's Windows PC

The Android phone owns voice authorization, Google credentials, and the Project Manager workbook. The customer client has no credential entry and never reads or writes Windows Credential Manager or the owner's Google settings. Screen capture and approved computer actions run only on the customer's PC. Project reads and writes require approval on the phone.

## Carry the client on the phone

Copy `Bluey-Customer.exe` from the phone's `Download/Bluey` folder to a temporary folder on the PC using Android's **USB → File transfer** option. Android exposes MTP storage, not a conventional USB drive letter; Windows must copy the executable locally before running it. Bluey does not change the phone's USB mode or auto-run software. The customer must authorize running the client and local network pairing. The app is unsigned; do not bypass organizational application restrictions.

Run the copied executable. It needs no installer or administrator account. Connect the PC and phone to the same trusted network (or a phone hotspot), start pairing, then choose the PC on the phone. USB supplies the file; pairing uses the local network. Computer control starts disabled and every action needs local approval. Settings-window close keeps Bluey in the tray; **Quit Bluey** stops sharing. Quit and delete the copied executable when finished. Windows may retain ordinary OS execution history/cache; this is not a forensic no-trace mode.

## One-time phone credential setup on the trusted PC

1. Update and open the phone app once to create its Android Keystore key pair.
2. With this development APK and authorized USB debugging, run `Windows/provision-phone.py --adb <adb.exe> --serial <phone serial>` from Windows' Python environment. It reads existing Bluey credentials locally and sends only an RSA-OAEP/AES-GCM encrypted profile to this phone's app-private storage. The private key is non-exportable Android Keystore material; backup is disabled. The script does not write a plaintext profile or print credentials.
3. On the phone, open **Phone settings → Activate prepared credentials**, then **Test phone connections**. Restart voice. OpenAI token creation and Google refresh now run on the phone; no durable credential is sent to a desktop. Existing Google consent is reused; revoked or expired authorization requires trusted-PC reauthorization and reprovisioning.
4. Verify phone voice and a phone-approved project read before removing the trusted PC's credential copies. Provisioning intentionally preserves recovery copies until verified. Never put client JSON, tokens, or credential exports in the customer download folder.

This initial provisioning is for the current debug build; a signed production release needs an authenticated import UI rather than `run-as`. The portable client is not an unattended agent and has no autostart or background service.

## Build

From `Windows/` after installing `requirements.txt` and PyInstaller:

```powershell
python -m PyInstaller --clean --noconfirm --windowed --onefile --name Bluey-Customer --icon bluey/assets/bluey.ico --add-data "bluey/assets;bluey/assets" --paths . --collect-submodules keyring.backends --collect-submodules pywinauto --hidden-import comtypes --hidden-import pyautogui --hidden-import pystray._win32 launcher_customer.py
```

The complete portable artifact is `dist/Bluey-Customer.exe`. Do not bundle `.venv`, local settings, API keys, Google client JSON, or credentials.

## Windows text control

`type_text` supports Unicode, emoji and line breaks (CRLF/CR normalized to LF), with a 2000-character limit. It uses Windows Unicode keyboard input without replacing the clipboard. Tabs and other control characters are rejected. Release modifier keys before approving typing. The target must be a normal desktop window with a verified non-password field; protected/elevated windows may reject input.

The approval dialog closes before Bluey restores and verifies the original window's focus. If the target closes or the phone disconnects, the action is cancelled. Reconnect and re-enable computer control after a disconnect; restart voice after changing the control setting to reload tools. Capture and action coordinates still refer to the primary display.

Approvals appear in a Bluey character bubble beside the companion on the current monitor, clamped inside that display even with negative monitor coordinates. The phone shows waiting/checking/action-result status. Field verification runs on one dedicated COM MTA worker with a2.5-second timeout; unknown/password fields still refuse typing. Concurrent actions return a busy result immediately instead of waiting behind an unresponsive check.
