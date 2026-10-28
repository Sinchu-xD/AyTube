# AyTube Cookie Exporter (Browser Extension) 🍪

A lightweight, cross-platform browser extension to export YouTube session cookies in standard Netscape format for **AyTube**, **yt-dlp**, and **curl** in a single click.

**Supported Browsers:**  
✅ **Android:** Kiwi Browser, Mises Browser, Firefox Android  
✅ **Desktop:** Chrome, Brave, Edge, Firefox, Chromium

---

## 📱 Android Setup (Kiwi Browser)

Normal Chrome for Android does not support extensions, but **Kiwi Browser** (free on Play Store) has full native extension support:

1. **Install Kiwi Browser** from Google Play Store if you don't have it.
2. Download or copy the `extension` folder (or `extension.zip`) to your phone.
3. In Kiwi Browser, tap the **3 dots menu (⋮)** in the top-right -> tap **Extensions**.
4. Turn ON **"Developer mode"** (top-right toggle).
5. Tap **`+ (from .zip / .crx / user.js)`** and select your `extension.zip` (or select the `extension` folder).
6. Now open [m.youtube.com](https://m.youtube.com) and log in to your YouTube account.
7. Tap the **3 dots menu (⋮)**, scroll down to the bottom, and tap **AyTube Cookie Exporter**.
8. Tap **"Download cookies.txt"**.
9. The `cookies.txt` file is downloaded straight into your phone's `Downloads` folder!

---

## 🦊 Firefox Setup (PC & Android)

### On Firefox Desktop:
1. Open Firefox and type `about:debugging#/runtime/this-firefox` in the address bar.
2. Click **"Load Temporary Add-on..."**.
3. Select `manifest.json` from the `extension` folder.
4. Open [youtube.com](https://www.youtube.com) and click the extension icon to export.

### On Firefox Android (Nightly):
1. Go to Settings -> About Firefox Nightly -> Tap logo 5 times to enable debug menu.
2. Go to Custom Add-on collection and install via collection or use Kiwi Browser on Android (Kiwi is recommended as it installs in 10 seconds).

---

## 💻 Desktop Setup (Chrome / Brave / Edge)

1. Open your browser extensions page:
   - **Chrome:** `chrome://extensions/`
   - **Brave:** `brave://extensions/`
   - **Edge:** `edge://extensions/`
2. Turn on **Developer mode** (top-right toggle).
3. Click **"Load unpacked"** (top-left).
4. Select the `extension` folder.
5. Open [youtube.com](https://www.youtube.com), click the extension icon -> **"Download cookies.txt"**.

---

## 🛡️ Privacy & Security

- **100% Offline & Local:** Runs completely inside your browser sandbox.
- **Zero External Network Calls:** Does not transmit your cookies to any remote server.
- **Open Source:** Clean, readable HTML and vanilla JavaScript.
