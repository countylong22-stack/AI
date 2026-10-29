# Rooster Android companion

Rooster AI is intended to be a voice-enabled Android companion. It provides text chat, speech-to-text through Android's speech recognition service, spoken replies through Android TextToSpeech, PC status, bounded autonomous engineering task submission, task progress, and emergency stop. The **AI conversation service and engineering engine run on your Windows PC**; the phone is the interface, not a separate local AI engine. Speech recognition availability depends on Android's installed speech service and network/device settings.

## Build and install the APK

1. Open the [Rooster Android build workflow](https://github.com/countylong22-stack/AI/actions/workflows/build-android-app.yml).
2. Open the latest successful run for your branch or pull request.
3. Under **Artifacts**, download `Rooster-Autonomous-Engineer-Android`.
4. Extract the ZIP and install `app-debug.apk` on your Android phone. Android may ask you to allow installs from the browser or file manager you used.

## Connect securely over your home network

The companion requires HTTPS for remote connections. Do not port-forward port 8765 to the internet.

1. On the Windows Rooster PC, find its private LAN IPv4 address with `ipconfig`. Example below: `192.168.1.20`.
2. Create a private certificate authority and a server certificate whose Subject Alternative Name contains that exact IP. Keep the CA private key and server private key off GitHub. Example OpenSSL workflow (replace the IP):

   ```powershell
   openssl genrsa -out rooster-ca.key 3072
   openssl req -x509 -new -key rooster-ca.key -sha256 -days 3650 -out rooster-ca.crt -subj "/CN=Rooster Home CA"
   openssl genrsa -out rooster-server.key 2048
   openssl req -new -key rooster-server.key -out rooster-server.csr -subj "/CN=192.168.1.20"
   @"
   subjectAltName=IP:192.168.1.20
   extendedKeyUsage=serverAuth
   "@ | Set-Content -Encoding ascii rooster-server.ext
   openssl x509 -req -in rooster-server.csr -CA rooster-ca.crt -CAkey rooster-ca.key -CAcreateserial -out rooster-server.crt -days 365 -sha256 -extfile rooster-server.ext
   ```

3. Transfer `rooster-ca.crt` to the phone and install it as a user CA certificate in Android security settings. Menu names vary by Android version. The app trusts system CAs and user-installed CAs, but refuses plain HTTP.
4. In PowerShell on the Rooster PC, set a long random token for the current session, then start the API from the repository folder:

   ```powershell
   $env:ROOSTER_API_TOKEN = "replace-with-a-long-random-secret"
   $env:OPENAI_API_KEY = "your-OpenAI-API-key"
   # Optional: set ROOSTER_CHAT_MODEL to a chat model enabled for your API account.
   # Optional: set ROOSTER_AGENT_MODEL to a model enabled for your autonomous agent.
   python mobile_server.py --host 0.0.0.0 --port 8765 --ssl-certfile rooster-server.crt --ssl-keyfile rooster-server.key
   ```

   Keep certificate and key paths correct for the directory you run the command from. Keep the API token private. Allow TCP 8765 through Windows Firewall only on your **Private** network profile if Windows prompts you.

5. Open the app. Enter `https://192.168.1.20:8765` using your PC's actual LAN IP and enter the same API token. Tap **CONNECT / CHECK STATUS**.
6. Under **TALK TO ROOSTER**, type a message and tap **SEND**, or tap **TALK** and speak. Android may ask for microphone permission. **VOICE ON/OFF** controls spoken replies. Ordinary chat does not execute commands.
7. To give Rooster engineering work, enter the objective under **ROOSTER ENGINEERING CONTROLS** and tap **RUN AUTONOMOUS TASK**. Tap **REFRESH TASK STATUS** to check progress. **EMERGENCY STOP** blocks further guarded actions. Reset only when you deliberately want to resume.

## Autonomy and limits

Rooster's autonomous coding loop plans, inspects eligible workspace files, proposes bounded changes, and runs tests, with a maximum of three iterations for tasks started through this mobile endpoint. RoosterGuard, protected-path restrictions, the audit log, runtime limits, and emergency stop remain in force. It is not unrestricted or guaranteed to solve every task. Review the resulting diff and evidence before relying on changes.

## Security notes

- Do not use this API on public Wi-Fi.
- Do not expose port 8765 to the public internet or configure router port forwarding.
- Use a fresh, private API token; never commit tokens, certificate private keys, or the CA private key.
- Chat history currently lives in the app session; it is sent to your own Rooster PC API for the model response.
- A task list is held in the running API process; task status IDs may no longer be available after restarting the API.
- The Android app build is a debug APK for testing, not a Play Store release.
