# Bluey for Android

An Android 8+ companion for a Mac or Windows Bluey desktop. Open this directory in Android Studio, use JDK 17+, install Android SDK 35, and run on a physical phone. Or build with the checked-in Gradle wrapper:

```sh
./gradlew assembleDebug testDebugUnitTest lintDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The debug APK is also produced by Android CI. Release signing is intentionally left to the owner's Android keystore; never commit a keystore or signing password.

Start Bluey on the desktop and put both devices on the same trusted Wi-Fi. The app discovers `_googly._tcp` services using Android NSD, remembers the selected desktop, reconnects its TCP link, and displays the blueberry with the desktop's gaze and mood. **Pair desktop** selects another host or accepts a manual IPv4 address and TCP port. Manual addresses must be entered again after restarting the app; discovered desktop selections are retained. Wi-Fi client isolation or multicast filtering can prevent discovery.

Bluey stays in landscape and supports either landscape rotation. Double tap Bluey to wake/sleep (or use the **Wake / sleep** button). Grant microphone permission when prompted. While awake, audio is continuously sent to OpenAI as conversation context, but no response is requested until you **hold to ask and release**. **Ask now** requests a reply to the spoken context without a hold gesture, for accessibility. A short chirp accompanies streamed text replies. Voice uses mono 24 kHz PCM and the same OpenAI Realtime model and token request as iOS. The phone never stores the desktop's OpenAI key. Tool calls run on the paired desktop; screenshot replies are sent back into the AI conversation.

Backgrounding the app closes the voice session and desktop link and stops the microphone. Returning to the app resumes discovery, with voice asleep. If the Internet voice connection drops or expires, the app visibly ends voice; double tap to start a new session. Automatic long-session Realtime recovery and archived meeting notes are not yet ported. Unsupported microphone sample rates or denied permissions are reported in the UI.

Pairing is unencrypted and unauthenticated to remain compatible with the Apple protocol. Use only trusted private networks. This Android app allows cleartext local TCP; OpenAI connections use verified TLS through OkHttp. Never expose the desktop port to the Internet.

## Device smoke test

1. Start the Mac or Windows host. Verify discovery, selection, and eye movement as you move the desktop pointer.
2. Disable Wi-Fi, reconnect it, and verify the desktop link reconnects. Switch hosts and verify stale replies do not update the new connection.
3. Deny microphone permission and verify the explanation. Grant it, double tap, hold a question for more than a second, and release. Verify the reply appears on desktop and phone.
4. Ask about the screen; verify a screenshot tool result and pointing. On Windows, enable computer control, restart voice, request an action, and test both **Decline** and **Allow**.
5. Background the phone during capture and verify Android's microphone indicator stops; return and verify voice is asleep.

These hardware and API checks are separate from compilation, lint, and local framing unit tests.

## Spoken replies on Android

Completed replies are read aloud through Android TextToSpeech while captions remain visible. Bluey prefers an installed offline English voice and uses the phone media volume; no additional OpenAI speech request or desktop key transfer is involved. The exact voice depends on the installed Android speech engine. Set media volume using the phone buttons.

Tap the top-right **•••** menu and **Test voice** to test playback without a desktop connection or API request. During playback Bluey's mouth animates and microphone frames are withheld from Realtime to avoid feeding its own speech back. Holding a new question, sleeping, leaving the app, or losing an active desktop connection stops speech. Missing voice data or playback failure leaves captions available and shows an error.

Implementation references: https://developer.android.com/reference/android/speech/tts/TextToSpeech and https://developer.android.com/reference/android/speech/tts/UtteranceProgressListener .
