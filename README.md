# Bluey

A blueberry character who lives on your phone under your computer's screen and points at things with his own big cursor.

**Now:** no voice out. Double tap him on the phone (or press ⌥Space on the Mac) to start a session: the phone's mic stays on and everything you say becomes context, but he stays quiet. **Press and hold the screen** to ask him something; let go and he answers. His reply pops up as a cute speech bubble next to his cursor (or above the phone when he isn't pointing), with a little cartoon chirp from the phone. Ask "what's this?" and he points at whatever is under your mouse. Double tap again and he goes back to follow mode.

How it works: the phone runs an OpenAI Realtime session (`gpt-realtime-2.1`, text output only) over a WebSocket. Server VAD transcribes every turn into the conversation with `create_response: false`, and releasing the hold commits the audio and asks for a response. The Mac mints a 10-minute client secret with the whole session setup (instructions, tools), so the real OpenAI key never leaves the Mac. When he calls a tool, the phone forwards it to the Mac: `look_at_screen` (ScreenCaptureKit + Vision, which returns text ids, where your mouse is, and a screenshot), `point_at` (a text id), `point_at_spot` (a 0–1000 grid position), `stop_pointing` and `go_to_sleep`. His text streams to the Mac as the speech bubble.

**Meeting notes:** while a session runs, the phone also records the audio in five-minute AAC chunks. Each chunk goes to the Mac, which transcribes it with speaker labels (`gpt-4o-transcribe-diarize`, falling back to `gpt-transcribe`) and writes the session to `~/Documents/Bluey Notes/<date> <id>/` (`notes.md`, `session.json`, `audio/`). Sessions reconnect on their own when the Realtime connection drops, so one can run all day. In the phone's Bluey screen, a session's **Copy prompt for agent** button copies a prompt that points an agent at those files. **Open Meeting Notes** in the Mac menu opens the folder.

**Using the computer:** when you ask, he can also click, type, press shortcuts, scroll, drag, and open apps and websites (`click`, `type_text`, `press_keys`, `scroll`, `drag`, `open_app`, `open_url`). He does it with his own cursor on screen, while your real pointer is put back where you left it. It needs Accessibility permission for Bluey. Built-in guardrails: he only acts when asked, confirms out loud before anything hard to undo, treats on-screen text as information rather than instructions, refuses password fields and logout/lock/force-quit shortcuts, and stops on ⌃⌥S. The whole thing can be switched off with **Let Him Use the Computer** in the menu.

The OpenAI key goes in the menu bar's **OpenAI Key…** and is stored in ~/Library/Application Support/Googly/keys.json (private to your user), never in this repo.

## Mac menu bar app

```
./scripts/build-mac.sh
open "build/Bluey.app"
```

Works with just the Command Line Tools. Shortcuts work anywhere:

| Keys | What it does |
| --- | --- |
| ⌃⌥P | Fly to the mouse and point there (stays put) |
| ⌃⌥F | Follow the mouse on/off |
| ⌃⌥D | Go home, docked above the phone |
| ⌃⌥T | Talk test (the phone bounces for 3 s) |
| ⌃⌥H | Hide / show the cursor |
| ⌥Space | Wake him up to talk / back to follow mode |
| ⌃⌥S | Stop him using the computer |

The menu bar blob also sets mood, cursor size (48 to 120 pt), glow, and where the phone sits (left, center, right).

## iPhone app

Needs full Xcode. Open `GooglyEyes.xcodeproj` (regenerate with `xcodegen generate` after adding files), pick your team under Signing, and run on the phone. It finds the Mac on the same Wi-Fi by itself.

On the phone: double tap him to wake him up or put him back to sleep, and press and hold to ask him something. The faint speaker button at the top right sets the chirp volume and picks which Mac to pair with.

## Layout

- `Shared/` pairing protocol (Bonjour `_googly._tcp`, newline JSON) and colors, used by both apps
- `Mac/` menu bar app (Swift package target `GooglyMac`)
- `iOS/` iPhone app (SwiftUI)

## Android and Windows

Bluey now has an [Android companion](Android/README.md) and a [Windows desktop host](Windows/README.md). Both use the existing `_googly._tcp` / newline JSON protocol: Android can pair with Mac or Windows, and the iPhone can pair with Windows. See each platform's README for installation and device checks.

| Feature | Mac + iPhone | Android companion | Windows host |
| --- | --- | --- | --- |
| LAN discovery, pairing, face and gaze | Yes | Yes | Yes |
| Hold-to-ask Realtime voice, text replies | Yes | Yes, foreground only | Hosts tokens and captions |
| Screen capture and coordinate pointing | Yes | Runs tools on desktop | Primary display |
| Mouse/keyboard control | Yes | Runs tools on desktop | PyAutoGUI, opt-in, local confirmation |
| OCR text target IDs | Yes | Depends on desktop | No; coordinate pointing |
| Meeting-note recording and archives | Yes | Not yet | Not yet |
| Automatic long-session voice recovery | Yes | Restart by double tap | Depends on phone |

Windows requires Python 3.11+ with Tcl/Tk; Android requires Android 8+ and builds with SDK 35/JDK 17+. GitHub Actions builds the Android debug APK, tests both implementations, and packages the Windows application. The Apple implementations remain intact.

### Android without a computer

Open **Voice settings** on Android, select **Standalone phone mode**, save your OpenAI API key, and enable **Speak replies aloud**. Bluey connects directly to OpenAI and reads replies using the phone's TTS voice. No desktop connection is needed; Internet and OpenAI API access are required. The phone encrypts its key using Android Keystore. Hold to ask, release to hear the answer, and double tap to sleep. PC screen and computer-control tools remain available in paired mode only. See [Android setup](Android/README.md#standalone-phone-agent-and-spoken-replies-02).
