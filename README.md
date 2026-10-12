<div align="center">

<img src="media/logo.png" width="125" alt="KepsLocker Logo" style="border-radius:24px; box-shadow: 0 8px 24px rgba(255, 70, 85, 0.4);"><br>

# ⚡ VALORANT INSTALOCKER PRO // KEPSLOCKER 🛡️
**ELITE TACTICAL DASHBOARD, INSTALOCKER & STEALTH ENGINE**  
*Created with precision by **By'KeplerB** & Advanced Agentic AI*

[![License: MIT](https://img.shields.io/badge/License-MIT-4bc51d?style=for-the-badge)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Status: Operational](https://img.shields.io/badge/Status-Operational-00f591?style=for-the-badge)](https://github.com/Keplorions/Valorant-InstaLocker)
[![Downloads](https://img.shields.io/github/downloads/Keplorions/Valorant-InstaLocker/total?style=for-the-badge&color=ff7b00&logo=github)](https://github.com/Keplorions/Valorant-InstaLocker/releases)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/CguCqpgQrd)

---

### 📸 LIVE DASHBOARD PREVIEW
![Web Dashboard Preview](media/dashboard.png)

<p align="center">
  <b><a href="#-english-documentation">🇺🇸 English Documentation</a></b> &nbsp;•&nbsp; 
  <b><a href="#-türkçe-dokümantasyon">🇹🇷 Türkçe Dokümantasyon</a></b> &nbsp;•&nbsp; 
  <b><a href="#-visual-showcase--screenshots">🖼️ Gallery</a></b> &nbsp;•&nbsp; 
  <b><a href="#-setup--installation">🚀 Installation</a></b>
</p>

</div>

---

## 🖼️ Visual Showcase / Ekran Görüntüleri

<table align="center" width="100%">
  <tr>
    <td width="50%" align="center">
      <b>🔍 Detailed Weapon & Skin Inspector</b><br>
      <img src="media/inventory_modal.png" alt="Skin Inspector Modal" width="100%">
    </td>
    <td width="50%" align="center">
      <b>👻 In-Game Stealth Presence Card</b><br>
      <img src="media/ingame_status.png" alt="In-Game Presence Card" width="100%">
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <b>💻 CLI Startup Mode Selection</b><br>
      <img src="media/cli_menu.png" alt="CLI Menu" width="100%">
    </td>
    <td width="50%" align="center">
      <b>🟢 CLI Online & Ready Status</b><br>
      <img src="media/cli_status.png" alt="CLI Online Status" width="100%">
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <b>🌙 Standalone Offline / Stealth Terminal Mode</b><br>
      <img src="media/cli_stealth.png" alt="CLI Stealth Mode" width="70%">
    </td>
  </tr>
</table>

---

## 🇺🇸 English Documentation

**Valorant InstaLocker PRO** *(KepsLocker)* is an elite tactical dashboard and agent auto-locking tool engineered for competitive VALORANT players. It combines millisecond-fast agent locking with in-depth match intelligence, live lobby skin inspection, anti-AFK protection, and a built-in stealth engine allowing you to appear offline to your friends list.

### 🌟 Key Features

* 🎯 **Instant Agent Auto-Lock (29 Agents):** Instantly selects and locks your favorite agent the moment match found packets arrive via local client websockets.
* 👻 **Stealth / Appear Offline Mode:** Hides your presence from your Riot friends list completely while setting a custom encrypted presence card in-game.
* 🛡️ **Anti-AFK Protection:** Subtle, randomized simulation mechanism preventing idle disconnects and queue bans in customs or unrated matches.
* 🎨 **Deep Weapon Skin & Inventory Scanner:** Scans and displays the weapon skins (Vandal, Phantom, Melee, Operator, etc.) of all 10 players in the lobby in real time.
* 📊 **Lobby & MMR Intelligence:** Real-time ranks, KP points, account levels, and premade party detection to know which players are queued together.
* 🌐 **Modern Glassmorphism Web UI:** Dark sci-fi aesthetic with interactive logo (click to instant reload), language toggle, and live map splash art.
* ⚡ **3 Flexible Launch Modes:**
  1. `[1]` **Standard Web Mode:** Web dashboard + auto-lock + live lobby stats.
  2. `[2]` **Web + Stealth Mode:** Full web dashboard while appearing offline to your friends.
  3. `[3]` **Standalone Stealth Mode:** Lightweight background engine without opening a web browser.
* 📦 **1-Click Portable EXE:** Compile directly into a single standalone `.exe` with the included `build_exe.bat`.

---

### 🛡️ Safety & Anti-Cheat Compliance

* **No Memory Hooking / No DLL Injection:** KepsLocker operates strictly through Riot's official **Local Client API** (`127.0.0.1` LCU/GLZ endpoints), exactly like legitimate companion apps (*Blitz.gg, Tracker.gg, Outplayed*).
* **Vanguard Friendly:** No game memory or file integrity is modified.
* *Disclaimer: While engineered to remain strictly within passive API boundaries, any third-party tool usage is at your own discretion.*

---

### 🚀 Setup & Installation

#### Option 1: Standalone Portable EXE (Recommended)
1. Download `KepsLocker.exe` from the [Releases](https://github.com/Keplorions/Valorant-InstaLocker/releases) tab.
2. Run `KepsLocker.exe` as Administrator.
3. Select your desired launch mode in the terminal.

#### Option 2: Running from Python Source
1. Ensure **Python 3.10+** is installed: [python.org](https://www.python.org/downloads/)
2. Clone the repository:
   ```bash
   git clone https://github.com/Keplorions/Valorant-InstaLocker.git
   cd Valorant-InstaLocker
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the application:
   ```bash
   python locker.py
   # Or double-click:
   Start.bat
   ```

#### Option 3: Compiling Your Own Single EXE
Double-click [`build_exe.bat`](file:///c:/Users/keplorion/Desktop/Valorant-InstaLocker-main/build_exe.bat). It will automatically install PyInstaller, embed the official icon (`app.ico`), bundle `stealth_engine.dat`, and generate `dist/KepsLocker.exe`.

---

> ⚠️ **IMPORTANT USAGE NOTE FOR OFFLINE / STEALTH MODE:**
> 1. **Do NOT open VALORANT first:** When using Offline Mode, start KepsLocker first; the tool will safely launch VALORANT with the proxy parameters.
> 2. **After quitting the game:** Always fully exit **Riot Client** from the Windows system tray (bottom-right taskbar); otherwise, offline mode stays active.

---

## 🇹🇷 Türkçe Dokümantasyon

**Valorant InstaLocker PRO** *(KepsLocker)*, VALORANT oyuncuları için tasarlanmış üst seviye bir ajan kilitleyici, taktiksel lobi analiz paneli ve çevrimdışı mod aracıdır. Milisaniyelik kilit motoru, tüm lobinin skinlerini gösteren envanter tarayıcısı, AFK koruması ve arkadaş listenize görünmez olmanızı sağlayan özel stealth motoru içerir.

### 🌟 Öne Çıkan Özellikler

* 🎯 **Milisaniyelik Ultra Hızlı InstaLock (29 Ajan):** Sıra bittiği ve ajan seçim ekranı açıldığı anda seçtiğiniz ajanı anında seçer ve kilitler.
* 👻 **Çevrimdışı (Görünmez) Mod:** Arkadaş listenizde tamamen çevrimdışı görünerek rahatsız edilmeden oyun oynamanızı sağlar.
* 🛡️ **Anti-AFK Koruması:** Özel maçlarda veya derecesiz oyunlarda AFK düşmenizi ve sıra cezası almanızı önleyen hafif hareket simülasyonu.
* 🎨 **Canlı Silah & Skin Tarayıcısı:** Lobideki 10 oyuncunun da elindeki silah skinlerini (Vandal, Phantom, Bıçak, Operatör vb.) canlı analiz eder ve detay kartında gösterir.
* 📊 **Lobi Rütbe & Parti Analizi:** Lobideki herkesin anlık rütbesini, KP puanını, hesap seviyesini ve kimlerin hazır grup (party) olarak girdiğini gösterir.
* 🌐 **Modern Glassmorphism Web Paneli:** Karanlık tema, tıklanınca F5 gibi sayfayı yenileyen interaktif logo, Türkçe/İngilizce dil seçeneği ve harita arka planı.
* ⚡ **3 Farklı Başlatma Seçeneği:**
  1. `[1]` **Normal Web Modu:** Web arayüzü + hızlı kilit + lobi takibi.
  2. `[2]` **Web + Çevrimdışı Mod:** Hem web panelini kullanın hem de arkadaş listenize çevrimdışı görünün.
  3. `[3]` **Sadece Çevrimdışı Mod:** Web tarayıcısı açılmadan sadece gizli modda sessizce oynamak isteyenler için.
* 📦 **Tek Tıkla Taşınabilir EXE Derleme:** `build_exe.bat` dosyasını çalıştırarak logonun da gömülü olduğu tek parça `.exe` üretebilirsiniz.

---

### 🛡️ Güvenlik & Ban Riski

* **Bellek Enjeksiyonu Yoktur:** Oyunun belleğine kod enjekte etmez (Memory injection / Hooking yapmaz). Riot'un kendi yerel istemci API protokollerini (`127.0.0.1` LCU/GLZ) kullanır. Blitz veya Tracker Network gibi resmi izinli programlarla aynı mimariyi paylaşır.
* **Vanguard Uyumludur:** Oyun dosyalarında herhangi bir değişiklik yapmaz.
* *Sorumluluk Reddi: Uygulama en pasif ve güvenli API yöntemleriyle geliştirilmiş olsa da, tüm 3. parti yazılımlarda olduğu gibi kullanım sorumluluğu son kullanıcıya aittir.*

---

### 🚀 Kurulum ve Çalıştırma

#### Seçenek 1: Tek Parça EXE Sürümü (Önerilen)
1. [Releases](https://github.com/Keplorions/Valorant-InstaLocker/releases) sekmesinden güncel `KepsLocker.exe` dosyasını indirin.
2. `KepsLocker.exe` dosyasını yönetici olarak başlatın.
3. Açılan terminal ekranından dilediğiniz başlatma modunu seçin.

#### Seçenek 2: Python Kaynak Kodundan Çalıştırma
1. **Python 3.10+** kurulu olduğundan emin olun: [python.org](https://www.python.org/downloads/)
2. Projeyi indirin veya klonlayın:
   ```bash
   git clone https://github.com/Keplorions/Valorant-InstaLocker.git
   cd Valorant-InstaLocker
   ```
3. Gereksinimleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
4. Programı başlatın:
   ```bash
   python locker.py
   # veya doğrudan:
   Start.bat
   ```

---

> ⚠️ **ÇEVRİMDISI (STEALTH) MOD İÇİN ÖNEMLİ KULLANIM KURALI:**
> 1. **Oyunu Önceden Açmayın:** Çevrimdışı mod kullanacaksanız VALORANT'ı önceden açmayın; önce KepsLocker'ı başlatın, oyun program tarafından otomatik açılacaktır.
> 2. **Oyundan Çıkışta:** Oyunu kapattıktan sonra görev çubuğunun sağ altındaki bildirim alanından **Riot Client** uygulamasını tamamen kapatın; aksi halde çevrimdışı mod açık kalmaya devam eder.

---

## ⚖️ License & Credits

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

<div align="center">

**Developed with ❤️ by By'KeplerB & AI Community** 🛡️🚀  
Join our community on [Discord](https://discord.gg/CguCqpgQrd) for updates, feature requests, and support!

</div>
