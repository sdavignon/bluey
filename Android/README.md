# Bluey for Android

An Android 8+ companion for a Mac or Windows Bluey desktop. Open this directory in Android Studio, use JDK 17+, install Android SDK 35, and run on a physical phone. Or build with the checked-in Gradle wrapper:

```sh
./gradlew assembleDebug testDebugUnitTest lintDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The debug APK is also produced by Android CI. Release signing is intentionally left to the owner's Android keystore; never commit a keystore or signing password.

Start Bluey on the desktop and put both devices on the same trusted Wi-Fi. The app discovers `_googly._tcp` services using Android NSD, remembers the selected desktop, reconnects its TCP link, and displays the blueberry with the desktop's gaze and mood. **Pair desktop** selects another host or accepts a manual IPv4 address and TCP port. Manual addresses must be entered again after restarting the app; discovered desktop selections are retained. Wi-Fi client isolation or multicast filtering can prevent discovery.

Landscape is recommended, though the face adapts to either orientation. Double tap Bluey to wake/sleep (or use the **Wake / sleep** button). Grant microphone permission when prompted. While awake, audio is continuously sent to OpenAI as conversation context, but no response is requested until you **hold to ask and release**. **Ask now** requests a reply to the spoken context without a hold gesture, for accessibility. A short chirp accompanies streamed text replies. Voice uses mono 24 kHz PCM and the same OpenAI Realtime model and token request as iOS. The phone never stores the desktop's OpenAI key. Tool calls run on the paired desktop; screenshot replies are sent back into the AI conversation.

Backgrounding the app closes the voice session and desktop link and stops the microphone. Returning to the app resumes discovery, with voice asleep. If the Internet voice connection drops or expires, the app visibly ends voice; double tap to start a new session. Automatic long-session Realtime recovery and archived meeting notes are not yet ported. Unsupported microphone sample rates or denied permissions are reported in the UI.

Pairing is unencrypted and unauthenticated to remain compatible with the Apple protocol. Use only trusted private networks. This Android app allows cleartext local TCP; OpenAI connections use verified TLS through OkHttp. Never expose the desktop port to the Internet.

## Device smoke test

1. Start the Mac or Windows host. Verify discovery, selection, and eye movement as you move the desktop pointer.
2. Disable Wi-Fi, reconnect it, and verify the desktop link reconnects. Switch hosts and verify stale replies do not update the new connection.
3. Deny microphone permission and verify the explanation. Grant it, double tap, hold a question for more than a second, and release. Verify the reply appears on desktop and phone.
4. Ask about the screen; verify a screenshot tool result and pointing. On Windows, enable computer control, restart voice, request an action, and test both **Decline** and **Allow**.
5. Background the phone during capture and verify Android's microphone indicator stops; return and verify voice is asleep.

These hardware and API checks are separate from compilation, lint, and local framing unit tests.

## Standalone phone agent and spoken replies (0.2)

Bluey can now run on Android without pairing to any computer. Open **Voice settings**, leave **Standalone phone mode (no PC)** selected, enter your own OpenAI API key, and enable **Speak replies aloud**. The phone encrypts the saved key with a non-exportable Android Keystore AES-GCM key; the saved preference contains only ciphertext and an IV. Backups and transfers exclude these app preferences. The key entry dialog blocks screenshots and does not save its text as view state. **Remove phone key** removes the saved credential. Never put this key in repository files or send it in chat.

Standalone mode is the default. The phone connects directly to OpenAI over a verified-TLS WebSocket and configures its own agent session. Internet access and an OpenAI account with access to the configured Realtime model are required; API usage is billed to that account. This is independent of the PC, not an offline language model. The agent answers questions and helps with reasoning, planning and writing, but cannot inspect or operate a PC, control phone apps, read local files, or search the live web in standalone mode. Only the local `go_to_sleep` tool is advertised.

Tap **Wake / sleep** or double tap the face, grant microphone permission, hold to ask and release. Replies appear as text and are read aloud through Android's system TTS engine. Microphone audio is not sent while TTS is speaking (including a short echo tail), and holding again interrupts playback. Sleep and backgrounding stop both microphone capture and speech. If no installed TTS voice supports your phone's language, the reply stays visible and the app asks you to check Android's text-to-speech settings. Long replies are queued in engine-supported chunks. Turning **Speak replies aloud** off keeps text-only replies.

To use a computer again, uncheck standalone mode in **Voice settings**, save, and pair the desktop. That mode obtains an ephemeral token from the desktop and can run its tools; the phone key is not sent to the desktop. Spoken replies work in paired mode too. Losing desktop discovery or a desktop connection cannot terminate a standalone session.

Validate on your phone with the PC switched off: save the key, wake Bluey, ask an ordinary question, hear the answer, interrupt a reply by holding, then say "go to sleep" and verify speech finishes before the microphone stops. Repeat after denying microphone permission, with spoken replies off, and with the phone backgrounded. These real microphone, Keystore, TTS, and account checks require the device; local JVM tests validate the session configuration and computer-tool boundary.
