"""
╔═══════════════════════════════════════════════════════════════╗
║           VALORANT INSTA-LOCKER v1.0                         ║
║           Maç bulunduğu gibi ajanını kilitle!                ║
╚═══════════════════════════════════════════════════════════════╝
"""
import requests
import urllib3
import time
import base64
import os
import json
import random
import ctypes
import threading
import webbrowser
import logging
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template_string, jsonify, request
import subprocess
import atexit
from ctypes import wintypes
try:
    from pypresence import Presence
    PYPRESENCE_AVAILABLE = True
except ImportError:
    PYPRESENCE_AVAILABLE = False

# Stealth / Görünmez Mod Yönetimi (KEPSLOCK Motoru)
STEALTH_PROCESS = None
STEALTH_EXE_PATH = None

def start_stealth_engine():
    """Özel 'KEPSLOCK ACTIVE' stealth motorunu arka planda geçici dosyadan çalıştırır."""
    global STEALTH_PROCESS, STEALTH_EXE_PATH
    try:
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        dat_path = os.path.join(base_dir, "stealth_engine.dat")
        if not os.path.exists(dat_path):
            # Proje ana dizin fallback
            dat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stealth_engine.dat")

        if not os.path.exists(dat_path):
            console.print("[red](!) stealth_engine.dat bulunamadı![/red]")
            return False

        # Varsa eski açık Riot/Valorant oturumunu sonlandır
        os.system("taskkill /f /im VALORANT.exe /im VALORANT-Win64-Shipping.exe /im RiotClientServices.exe /im kepslock_core.exe >nul 2>&1")
        time.sleep(1)

        import tempfile
        temp_dir = tempfile.gettempdir()
        STEALTH_EXE_PATH = os.path.join(temp_dir, f"kepslock_core_{os.getpid()}.exe")
        try:
            with open(dat_path, "rb") as f_in, open(STEALTH_EXE_PATH, "wb") as f_out:
                f_out.write(f_in.read())
        except Exception as write_err:
            STEALTH_EXE_PATH = os.path.join(temp_dir, f"kepslock_core_{int(time.time())}.exe")
            with open(dat_path, "rb") as f_in, open(STEALTH_EXE_PATH, "wb") as f_out:
                f_out.write(f_in.read())

        # Valorant'ı stealth engine üzerinden başlat
        STEALTH_PROCESS = subprocess.Popen([STEALTH_EXE_PATH, "VALORANT"], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return True
    except Exception as e:
        console.print(f"[red]Görünmez mod motor hatası: {e}[/red]")
        return False

def stop_stealth_engine():
    """Çıkışta stealth motorunu ve geçici dosyayı temizler."""
    global STEALTH_PROCESS, STEALTH_EXE_PATH
    if STEALTH_PROCESS:
        try:
            STEALTH_PROCESS.terminate()
        except:
            pass
        STEALTH_PROCESS = None
    if STEALTH_EXE_PATH and os.path.exists(STEALTH_EXE_PATH):
        try:
            os.remove(STEALTH_EXE_PATH)
        except:
            pass
        STEALTH_EXE_PATH = None

atexit.register(stop_stealth_engine)

# Discord Rich Presence Ayarları
DISCORD_CLIENT_ID = "1521660514139115610"
DISCORD_PUBLIC_KEY = "a42114f295f8f986494b0d800164957d8bd755c6e359f8d48593d0c37bdd5cf1"
DISCORD_RPC = None
RPC_START_TIME = int(time.time())
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.live import Live
from rich.layout import Layout
from rich.align import Align

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
console = Console()

# Flask App Initialized
app = Flask(__name__)
# Suppress Flask Logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ----------------- ASSET CACHES -----------------
SKIN_CACHE = {}     # uuid -> {"name": str, "icon": str}
RANK_ASSETS = {}    # tier_id -> icon_url
AGENT_ASSETS = {}   # agent_name -> icon_url
WEAPON_ASSETS = {}  # uuid_prefix -> icon_url

def heal_url(url):
    """Ensure Valorant-API URLs have a filename or extension to avoid 404s"""
    if not url or not isinstance(url, str): return ""
    if "valorant-api.com" in url and not url.lower().endswith(".png"):
        # Most skin/roma icons are /displayicon.png
        if not url.endswith("/"): url += "/"
        url += "displayicon.png"
    return url

def fetch_skin_database():
    """Valorant-API'den skin veritabanını indir (İsim ve Resim)"""
    global SKIN_CACHE
    try:
        console.print("[dim]Skin veritabanı indiriliyor...[/dim]")
        r = requests.get("https://valorant-api.com/v1/weapons/skins", params={"language": "tr-TR"}, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            base_count = 0
            level_count = 0
            chroma_count = 0
            
            for skin in data:
                uuid = skin.get("uuid")
                name = skin.get("displayName")
                icon = heal_url(skin.get("displayIcon"))
                
                # v38.4: Robust Level 1 Fallback (Some base skins lack top-level icons)
                if not icon:
                    levels = skin.get("levels", [])
                    if levels:
                        icon = heal_url(levels[0].get("displayIcon") or levels[0].get("fullRender"))
                
                # Base skin
                if uuid: 
                    SKIN_CACHE[uuid] = {"tr": name, "en": name, "name": name, "icon": icon}
                    base_count += 1
                
                # Levels
                for item in skin.get("levels", []):
                    item_uuid = item.get("uuid")
                    if item_uuid:
                        item_icon = heal_url(item.get("displayIcon") or item.get("fullRender")) or icon
                        SKIN_CACHE[item_uuid] = {"tr": name, "en": name, "name": name, "icon": item_icon}
                        level_count += 1
                
                # Chromas
                for item in skin.get("chromas", []):
                    item_uuid = item.get("uuid")
                    if item_uuid:
                        item_icon = heal_url(item.get("displayIcon") or item.get("fullRender")) or icon
                        SKIN_CACHE[item_uuid] = {"tr": name, "en": name, "name": name, "icon": item_icon}
                        chroma_count += 1

            console.print(f"[green]Skin assets: Base={base_count}, Levels={level_count}, Chromas={chroma_count}, Total={len(SKIN_CACHE)}[/green]")
            return True
    except Exception as e:
        console.print(f"[red]Skin indirilemedi: {e}[/red]")
    return False

def fetch_agent_assets():
    global AGENT_ASSETS
    try:
        r = requests.get("https://valorant-api.com/v1/agents", params={"language": "tr-TR", "isPlayableCharacter": "true"}, timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", [])
            for agent in data:
                AGENT_ASSETS[agent.get("displayName")] = heal_url(agent.get("displayIcon"))
            console.print(f"[green]Agent assets: {len(AGENT_ASSETS)} loaded[/green]")
    except: pass

def fetch_rank_assets():
    global RANK_ASSETS
    try:
        r = requests.get("https://valorant-api.com/v1/competitivetiers", timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", [])
            # Iterate backwards to find the latest valid episode with tiers
            for episode in reversed(data):
                tiers = episode.get("tiers", [])
                if tiers and len(tiers) > 5:
                    for tier in tiers:
                        tier_id = tier.get("tier")
                        icon = tier.get("largeIcon") or tier.get("smallIcon")
                        if tier_id is not None and icon:
                            RANK_ASSETS[tier_id] = icon
                    break
    except: pass

# ----------------- WEB UI TEMPLATE -----------------
WEB_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VALO LOCKER PRO</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAHgklEQVR4nHWXXYhdVxXHf3ufj3vOnclkJmNikkqNKFIVo4gPgqIgFhSt+lTBQqDYJ6EIgpXqgz5UxBdBBR8ERYpKBT9qogWV+hIpitBKSZNS0aL1ITFJp53M3Hu+9t6y1t7n3rlJembOPV97r7X2Wv//WmubzeOnggH058BhTHwRgtxDSA8Gg/7rS3kbn4Pex2N5K5MBPwpdfS1HHievKo9CgipJdmAx2CwjyzK9WvkwGimn93jvcIPDB48XoSrXYOyqgbrgdM1XLBOFNxkiRuR5TlGUqjxKS7LTrwrIwcj7icc7R993DMOwonixuGSBfIkG3OSh8ciynMlkolcZ7X0gBLdw48pSxmgYg7U5VZXjhp62a3EuzdEAhoNmk99OvQwrioJyUumT836pyKDuN1b9uvCchiCI8EDw8b3NCuo6p20b9Uh8O1obp+cRYRLvpRllWVJOJjgXBS5MC4HMZjRtS9t2S3ACk7Kk0jlugQ25F49UVa3XrmtX/WDEgAS28SjKiSofhgTdEaQhKBZe3b3BW978Ju688w0KuBiqjP+89F/++a8X2Th0iMENC4+KZ4YQVKbI6PpuJcz5wXCKAln90KeYHQRLlvHyzg7vfc+7eezRH/D6Y8dWBF2+8j8+c+YBnv77s2xtHsa5kXvRCNdHI4Qp/SAGJhWbJ06pF621TOuprlZotPSKgAqapuX0O97Oz3/yQ163vc2PHv0pOzuvqHHbW1vcf+azXL16jXvPPMCF5y5RVaJMsJPi7QUTVqkyn81Vh0xegLAsCo2dUEeUj/SRaAn1ZNJDX3xQlX/5q1/n29/5vsZcRrVtywsv/INvPvI1vvSFz3PvfZ+j1tUeoKCBwTmKQihdKDtkiVZXbyxZXuDE9TJJTrHQB6wAzwcmMlDiOQyc+/VZTh7Z5MT2Fie3NzlxZJNzj5+NxvtAKcD1DisekNMlmXLbOw31mHGsgijP9NH5iGDFXFq9DZ7ceCbBs7F+SCcfW1+jco7JEM/aOY6tr+u3jfV1HVuYgFUGBU08MSkGXBBmyIKzlIhCRLGTJDOSU8dG+lkTKFygynPOP/knrl25TDGbsS4JRwzGUEq23J9x7le/4eKzF6jzksIHRb9PxWAMhmiRvCLJbegHzNaJU6Gup2qAIHSEvqRVWYW4forhW2sbHGlarrQNjxWWB6cbHEreuoHne/s3uG8IHC0nXK8nPLy3y74JdAE69cOyuGWZxVrDfD4jV7Qbgw9umd9DTBXKfQxd8PTe876tI/r5wu51Xd07i1JnPNnNeVdWcM+RbbX/8f1dOi9hMIz5L9UlPYQdktA0bS8q2kgZRa7cx2cJxRrwy3bGXt/j3cA9Zc3Pmj2+u7/LzHt+38z52KTWInSj6/hFM9M5Kk/Sc7pGcKfnZI8d/aJ/wROMj1dhX4hxPGrgJIY/d3OtA6fLkoLAiczykpekEjhdlFgD57uGO4zhqDUMKkfOJF+xkPQkr9ioPNbIIKeXawRLGkAfAp+opvy1a2nVU4aPT6ZccY6zzT4fLmvtFxrv+UvX8MlqTcfp6tLi4xllR1rElzY2DlIPEveT6+PpNQ/MQ+CuolTQPdU36rsPlhUXh55/O8eHpGoaeKpr2LKWt2YFTQpf7KKSbG2NPMaO1TCI/BgThd2oXN20jNfY3UyM4XfNvr6f2owPFBPeX1TUNtN3TzT71AlT48Kiy5M/hepeiGkUiNHDqWwKNZbKR8aCEFP4URq4w+Y803U8P/RKq7urKXdXtY671Lc83beczHJKa3Ah6LxRkjh4pIPmHSnbgUhDKZ95XmvOV8tH5SLEwCzA+XbOp9c2qAycm+9xV16yLStPaD433+eh9U0+Ot3gt7NdZmpAND7mgIQp7TNt6huIHvAuNpRSKKKLkuuBgYDg/OHdHb7x6jU+Uq1RGcOloY2NhzFc7Fqmxui3R165yld2X9Y5mgljx6oMEB1ZketVKyUHmtKu66jqCms7xUJMoEYZIPSSavHj2Q0u9q1S7o/NjLeV0rLBH5p9TThnrl/mb31Lbiwtnl7CPlZ1L92U1XrRNBHI2vCOSUEsktw8qWqa2V7KjoFBvRcZvIbhmb7n+b7nqLV8qtZ0wxPNjOveaaiksu6FgKBEvOAlqyYZIlt0jKtX8B8+/saVvrmeVLjgaeczjVXMVgGpXZKWxf2V4DgEjmfyBS47SWDQBGhVsVQ9g0+1QhTW06nKG1e/aBMO32SACUZDISBp503sjOQ/eDVCYFekChi74Lhp6UbFCjxDUOWxsZGmVFgmypdN+WsYIIcYONGWHJr5XEGju6TkDUlOgl57gPNRacRNVOyxNqOqhV3QqvJbj3zlKbXoMlCsLYuSem3K0Hb0XRebS9knJGNUveaolGJTAhccSAOal6V6UgB+y67ntgaE1R5OWujMWYqyJC9KBtfj+kE7p7GpHO02VvaOBVmek+eFur5r27ipeQ3ltxpw82GkTfO4Zq7ulNa8rKRFOdCvjzFLWgRw0qRqc5PwsxS3TEgLA8ZdilyXm6blMO2QNc6ervfQp/3fbXbHkdJpP69hWn5fhGxFi+H/9HGBlO6C0NMAAAAASUVORK5CYII=">
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root { 
            --bg: #0b1119; 
            --panel: rgba(20, 29, 41, 0.6); 
            --accent: #ff4655; 
            --accent-glow: rgba(255, 70, 85, 0.5);
            --text: #ece8e1;
            --success: #00f591;
            --ally-bg: rgba(0, 245, 145, 0.05);
            --enemy-bg: rgba(255, 70, 85, 0.05);
            --card-border: rgba(255, 255, 255, 0.05);
        }
        
        body { 
            background-color: var(--bg);
            background-image: linear-gradient(rgba(11, 17, 25, 0.8), rgba(11, 17, 25, 0.8)), 
                              url('https://media.valorant-api.com/maps/2c9d57ec-4431-9c5e-2939-8f9ef6dd5cba/splash.png');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: var(--text); 
            font-family: 'Inter', sans-serif; 
            margin: 0; padding: 20px; 
            min-height: 100vh;
        }

        .container { max-width: 1600px; margin: 0 auto; padding: 0 10px; }
        
        /* Advanced Glassmorphism */
        .glass-panel {
            background: var(--panel);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
            padding: 24px;
            margin-bottom: 24px;
            transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        header { 
            display: flex; justify-content: space-between; align-items: center; 
            margin-bottom: 30px; 
            padding: 25px 30px;
            border-bottom: 2px solid rgba(255,70,85,0.2);
            position: relative;
            overflow: visible;
        }
        
        header::after {
            content: ''; position: absolute; bottom: 0; left: 0; width: 100%; height: 1px;
            background: linear-gradient(90deg, transparent, var(--accent), transparent);
        }
        
        .header-logo-container {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .header-logo {
            width: 54px;
            height: 54px;
            border-radius: 14px;
            border: 2px solid rgba(255, 70, 85, 0.4);
            box-shadow: 0 0 15px rgba(255, 70, 85, 0.25);
            background: rgba(11, 17, 25, 0.8);
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            user-select: none;
            object-fit: cover;
            display: block;
        }
        .header-logo:hover {
            transform: scale(1.08) rotate(-2deg);
            border-color: var(--accent);
            box-shadow: 0 0 25px var(--accent-glow);
        }
        .header-logo:active {
            transform: scale(0.95);
        }

        h1 { margin: 0; font-family: 'Rajdhani', sans-serif; font-size: 2.8em; text-transform: uppercase; letter-spacing: 2px; }
        .version-badge { font-size: 0.35em; vertical-align: middle; background: var(--accent); color: #fff; padding: 4px 10px; border-radius: 4px; box-shadow: 0 0 15px var(--accent-glow); margin-left: 10px; }
        
        .status-pill { background: rgba(0,0,0,0.4); padding: 10px 25px; border-radius: 40px; font-weight: 700; border: 1px solid rgba(255,255,255,0.05); display: flex; align-items: center; gap: 12px; font-family: 'Rajdhani', sans-serif;}
        .indicator { width: 12px; height: 12px; border-radius: 50%; background: #444; transition: 0.4s; }
        .indicator.active { background: var(--success); box-shadow: 0 0 15px var(--success); }

        /* Modern Language Dropdown (v44.11 Premium) */
        .lang-dropdown { position: relative; z-index: 1000; }
        .lang-dropdown-btn {
            display: flex; align-items: center; gap: 8px;
            background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
            padding: 8px 14px; border-radius: 8px; cursor: pointer;
            transition: 0.2s cubic-bezier(0.4, 0, 0.2, 1); font-family: 'Rajdhani', sans-serif; font-weight: 700;
            color: #ccc; font-size: 0.9em; letter-spacing: 1px;
            text-transform: uppercase;
        }
        .lang-dropdown-btn:hover { 
            background: rgba(255,70,85,0.08); 
            border-color: rgba(255,70,85,0.4); 
            color: #fff;
            box-shadow: 0 0 20px rgba(255, 70, 85, 0.1);
        }
        .lang-dropdown-btn svg { width: 16px; height: 16px; opacity: 0.8; }
        .lang-dropdown-btn img { width: 20px; height: 14px; border-radius: 2px; object-fit: cover; opacity: 0.8; }
        .lang-dropdown-menu {
            position: absolute; top: 100%; right: 0; margin-top: 12px;
            background: rgba(15,20,30,0.95); backdrop-filter: blur(25px);
            border: 1px solid rgba(255,255,255,0.1); border-radius: 12px;
            min-width: 100px; overflow: visible;
            opacity: 0; visibility: hidden; transform: translateY(-10px);
            transition: 0.2s cubic-bezier(0.4, 0, 0.2, 1); 
            box-shadow: 0 20px 50px rgba(0,0,0,0.7);
            padding: 6px;
        }
        /* Triangle Pointer */
        .lang-dropdown-menu::before {
            content: ''; position: absolute; top: -6px; right: 20px;
            width: 12px; height: 12px; background: rgba(15,20,30,0.95);
            border-top: 1px solid rgba(255,255,255,0.1);
            border-left: 1px solid rgba(255,255,255,0.1);
            transform: rotate(45deg);
        }
        .lang-dropdown.open .lang-dropdown-menu { opacity: 1; visibility: visible; transform: translateY(0); }
        .lang-option {
            display: flex; align-items: center; gap: 12px;
            padding: 10px 14px; cursor: pointer; transition: 0.2s;
            font-family: 'Rajdhani', sans-serif; font-weight: 700; color: #888;
            border-radius: 8px; margin-bottom: 2px;
            position: relative;
        }
        .lang-option:last-child { margin-bottom: 0; }
        .lang-option:hover { 
            background: rgba(255,255,255,0.05); 
            color: #fff; 
        }
        .lang-option:hover::after {
            content: ''; position: absolute; left: 0; top: 20%; height: 60%; 
            width: 3px; background: var(--accent); border-radius: 0 4px 4px 0;
            box-shadow: 0 0 10px var(--accent-glow);
        }
        .lang-option.active { color: #fff; background: rgba(255,70,85,0.1); }
        .lang-option.active::after {
            content: ''; position: absolute; left: 0; top: 20%; height: 60%; 
            width: 3px; background: var(--accent); border-radius: 0 4px 4px 0;
        }
        .lang-option img { width: 20px; height: 14px; border-radius: 2px; object-fit: cover; filter: grayscale(0.2); transition: 0.3s; }
        .lang-option:hover img { filter: grayscale(0); }

        .grid { display: grid; grid-template-columns: 380px 1fr; gap: 24px; align-items: start; }
        @media (max-width: 1200px) { .grid { grid-template-columns: 1fr; } }

        /* Premium Agent Selector */
        .agent-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; max-height: 550px; overflow-y: auto; padding: 10px; }
        .agent-btn { 
            position: relative; aspect-ratio: 1; cursor: pointer; 
            transition: 0.3s; border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1);
            background: rgba(0,0,0,0.4);
        }
        .agent-btn img { width: 100%; height: 100%; object-fit: cover; opacity: 0.7; transition: 0.3s; }
        .agent-btn:hover { border-color: rgba(255,255,255,0.4); transform: translateY(-3px); }
        .agent-btn:hover img { opacity: 1; }
        .agent-btn.active { border-color: var(--accent); box-shadow: 0 0 20px var(--accent-glow); transform: scale(1.05); z-index: 5; }
        .agent-btn.active img { opacity: 1; }

        #agent-grid { 
            display: grid; 
            grid-template-columns: repeat(5, 1fr); 
            gap: 10px; 
            margin-bottom: 20px;
        }
        .agent-btn {
            width: 100%;
            aspect-ratio: 1;
            background: rgba(0,0,0,0.2);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 8px;
            cursor: pointer;
            overflow: hidden;
            transition: 0.3s;
        }

        .big-btn {
            background: linear-gradient(135deg, var(--accent) 0%, #cc1422 100%);
            color: white; border: none; padding: 18px; border-radius: 12px;
            font-family: 'Rajdhani', sans-serif; font-size: 1.6em; font-weight: 800;
            width: 100%; cursor: pointer; margin-top: 20px;
            transition: 0.3s; text-transform: uppercase; letter-spacing: 2px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.3);
        }
        .big-btn:hover { transform: translateY(-3px); box-shadow: 0 15px 30px var(--accent-glow); filter: brightness(1.1); }
        .big-btn:active { transform: translateY(0); }

        /* Card Based Tables */
        .team-section { margin-bottom: 40px; }
        .team-header { 
            font-family: 'Rajdhani', sans-serif; font-size: 1.8em; margin-bottom: 20px; 
            display: flex; align-items: center; gap: 15px; 
            padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .team-ally { color: var(--success); }
        .team-enemy { color: var(--accent); font-weight: 800; }

        .player-row { 
            display: grid; 
            grid-template-columns: 65px 140px 280px 1fr; 
            align-items: center; gap: 10px;
            background: rgba(30, 35, 45, 0.6);
            border-radius: 12px; padding: 12px 20px;
            margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.05);
            transition: 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative; overflow: hidden;
            backdrop-filter: blur(8px);
        }
        .player-row:hover { 
            background: rgba(45, 50, 60, 0.8); 
            border-color: rgba(255,255,255,0.15); 
            box-shadow: 0 0 25px rgba(0,0,0,0.6), inset 0 0 15px rgba(255,255,255,0.02);
        }
        .player-row.ally { border-left: 3px solid var(--success); background: rgba(0, 245, 145, 0.07); }
        .player-row.enemy { border-left: 3px solid var(--accent); background: rgba(255, 70, 85, 0.07); }
        .player-row.me { border-left-width: 5px; }
        
        /* Ensure child elements don't trigger mouse events to prevent hover flickering, 
           EXCEPT for the skin deck where we want interactivity */
        .player-row > :not(.skin-deck) * { pointer-events: none; }
        .skin-deck { pointer-events: auto; }
        .skin-item { pointer-events: auto; }

        .skin-deck { display: flex; gap: 12px; justify-content: flex-end; }
        
        /* Rank Styling */
        .rank-card { display: flex; flex-direction: column; align-items: center; width: 65px; }
        .rank-icon-v10 { width: 48px; height: 48px; filter: drop-shadow(0 0 10px rgba(0,0,0,0.5)); transition: 0.3s; }
        .rank-name-v10 { 
            font-family: 'Rajdhani', sans-serif; font-size: 0.75em; font-weight: 800; 
            color: #fff; text-transform: uppercase; letter-spacing: 1px; 
            margin-top: 5px; text-align: center; width: 100%;
        }
        .rank-kp-v10 { 
            font-size: 0.65em; font-weight: 800; margin-top: 3px; color: #ffb100;
            text-transform: uppercase; opacity: 0.8; letter-spacing: 0.5px;
        }
        .rank-peak-v10 {
            font-family: 'Rajdhani', sans-serif;
            font-size: 0.6em;
            font-weight: 800;
            margin-top: 3px;
            color: #f59e0b;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            background: rgba(245, 158, 11, 0.12);
            border: 1px solid rgba(245, 158, 11, 0.35);
            border-radius: 4px;
            padding: 1px 5px;
            white-space: nowrap;
            display: inline-flex;
            align-items: center;
            gap: 3px;
            box-shadow: 0 0 6px rgba(245, 158, 11, 0.15);
            line-height: 1.1;
        }

        /* Profile Layout */
        .profile-card { display: flex; flex-direction: column; align-items: center; gap: 6px; width: 140px; border-right: 1px solid rgba(255,255,255,0.05); }
        .agent-icon-v9 { 
            width: 44px; height: 44px; border-radius: 50%; 
            border: 2px solid rgba(255,255,255,0.15); 
            object-fit: contain; background: transparent;
            filter: drop-shadow(0 0 8px rgba(0,0,0,0.6));
            transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .agent-icon-v9:hover { transform: scale(1.1) rotate(5deg); border-color: var(--accent); }
        
        /* Unified Agent Box (v44.33) */
        .agent-box-v13 { position: relative; width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; }
        .agent-box-v13.is-selecting { 
            animation: agentPulse 2s ease-in-out infinite;
            background-color: #1a222d;
            border-radius: 50%;
            border: 2px solid rgba(255,70,85,0.2);
            box-shadow: 0 0 15px rgba(255,70,85,0.1);
        }
        .agent-box-v13.is-selecting img { display: none !important; }
        
        @keyframes agentPulse { 
            0%, 100% { border-color: rgba(255,70,85,0.1); box-shadow: 0 0 5px rgba(255,70,85,0.05); } 
            50% { border-color: rgba(255,70,85,0.5); box-shadow: 0 0 25px rgba(255,70,85,0.25); } 
        }
        
        .mystery-q {
            display: none;
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            font-family: 'Rajdhani', sans-serif; font-size: 26px; font-weight: 900;
            color: #fff; text-shadow: 0 0 10px rgba(0,0,0,1);
            pointer-events: none; z-index: 10;
            opacity: 0.9;
        }
        .agent-box-v13.is-selecting .mystery-q { display: block; }
        
        .agent-name-v10 { font-family: 'Rajdhani', sans-serif; font-size: 0.9em; font-weight: 800; color: #fff; text-transform: uppercase; letter-spacing: 2px; }
        .level-badge { 
            font-size: 0.65em; background: #000; color: #ffb800; padding: 1px 6px; 
            border-radius: 4px; font-weight: 900; border: 1px solid #ffb800; 
            box-shadow: 0 0 10px rgba(255, 184, 0, 0.2);
        }
        .player-name-v9 { font-family: 'Rajdhani', sans-serif; font-size: 1.4em; font-weight: 800; color: #fff; letter-spacing: 1px; text-shadow: 0 2px 10px rgba(0,0,0,0.5); }
        .player-name-v9.is-me { color: var(--accent); text-shadow: 0 0 15px var(--accent-glow); }
        .player-name-v9.is-hidden-name { color: #94a3b8; font-style: italic; }
        .discriminator-v10 { font-size: 0.7em; color: #666; font-weight: 500; margin-left: 2px; }
        .party-tag {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            padding: 2px 7px 2px 6px;
            border-radius: 4px;
            border: 1px solid;
            width: fit-content;
            white-space: nowrap;
            line-height: 1;
            vertical-align: middle;
            transition: all 0.2s ease;
        }
        .party-tag-dot {
            width: 5px;
            height: 5px;
            min-width: 5px;
            min-height: 5px;
            border-radius: 50%;
            display: inline-block;
            flex-shrink: 0;
            position: relative;
            top: -1px;
        }
        .party-tag-text {
            display: inline-block;
            line-height: 1;
        }
        .incognito-tag {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            padding: 2px 7px 2px 6px;
            border-radius: 4px;
            border: 1px solid rgba(244, 63, 94, 0.45);
            background: rgba(244, 63, 94, 0.12);
            color: #fb7185;
            box-shadow: 0 0 8px rgba(244, 63, 94, 0.2);
            width: fit-content;
            white-space: nowrap;
            line-height: 1;
            vertical-align: middle;
            transition: all 0.2s ease;
        }

        /* Skin Card */
        .skin-item { 
            text-align: center; width: 100px;
            display: flex; flex-direction: column; align-items: center; gap: 4px;
        }
        .skin-icon-v6 { 
            height: 42px; width: 100%; 
            background-size: contain; background-repeat: no-repeat; background-position: center;
            background-color: rgba(0,0,0,0.2);
            border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);
            transition: 0.3s;
        }
        .skin-item:hover .skin-icon-v6 { transform: translateY(-2px) scale(1.05); border-color: var(--accent); background-color: rgba(255,255,255,0.05); }
        .skin-name-v6 { 
            font-size: 0.65em; color: #fff; font-weight: 700; 
            max-width: 90px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; 
            opacity: 0.9;
        }

        /* Notifications & Utils */
        .loading-text { font-size: 0.7em; color: #ffb800; font-weight: 800; letter-spacing: 1px; animation: pulse 1.5s infinite; }
        
        .lock-refresh-note {
            margin-top: 8px;
            font-size: 0.78em;
            color: #7a8b9e;
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            white-space: nowrap;
            letter-spacing: 0.4px;
        }
        
        /* Premium Empty State */
        .empty-state-wrapper { 
            display: flex; flex-direction: column; align-items: center; justify-content: center; 
            padding: 50px 20px; background: rgba(30, 35, 45, 0.4); border-radius: 12px;
            border: 1px dashed rgba(255,255,255,0.05); position: relative; overflow: hidden;
        }
        
        .radar-pulse {
            width: 14px; height: 14px; border-radius: 50%;
            position: relative; margin-bottom: 20px;
            animation: heartbeat 2s ease-in-out infinite;
        }
        @keyframes heartbeat { 
            0% { transform: scale(0.9); opacity: 0.8; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.8; }
        }
        
        .empty-title { font-family: 'Rajdhani', sans-serif; font-size: 0.9em; font-weight: 800; color: #fff; letter-spacing: 2px; margin-bottom: 5px; opacity: 0.8; }
        .empty-subtitle { font-size: 0.65em; color: #666; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
        @keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }
        
        .skin-spinner { width: 20px; height: 20px; border: 2px solid rgba(255, 184, 0, 0.1); border-top: 2px solid #ffb800; border-radius: 50%; animation: rotate 1s linear infinite; }
        @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

        /* Premium Toggle Switch */
        .toggle-container { display: flex; flex-direction: column; align-items: center; gap: 5px; }
        .toggle-switch { position: relative; width: 42px; height: 20px; }
        .toggle-switch input { opacity: 0; width: 0; height: 0; }
        .toggle-slider { 
            position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; 
            background: rgba(255,255,255,0.05); border-radius: 20px; transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
            border: 1px solid rgba(255,255,255,0.1); 
        }
        .toggle-slider:before { 
            position: absolute; content: ""; height: 14px; width: 14px; left: 2px; bottom: 2px; 
            background: #666; border-radius: 50%; transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .toggle-switch input:checked + .toggle-slider { background: rgba(0, 245, 145, 0.1); border-color: var(--success); }
        .toggle-switch input:checked + .toggle-slider:before { transform: translateX(22px); background: var(--success); box-shadow: 0 0 10px var(--success); }

        /* Language Switcher */
        .lang-switcher { display: flex; gap: 10px; margin-right: 20px; }
        .lang-btn {
            font-family: 'Rajdhani', sans-serif; font-size: 0.8em; font-weight: 800;
            color: #666; cursor: pointer; transition: 0.3s; padding: 4px 8px;
            border-bottom: 2px solid transparent; text-transform: uppercase;
        }
        .lang-btn:hover { color: #fff; }
        .lang-btn.active { color: var(--accent); border-color: var(--accent); }

        /* High-End Modal Animations (v44.60) */
        .info-modal {
            display: none; position: fixed; z-index: 1500; left: 0; top: 0; 
            width: 100%; height: 100%; background: rgba(0,0,0,0); 
            backdrop-filter: blur(0px); align-items: center; justify-content: center;
            transition: 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            pointer-events: none;
        }
        .info-modal.is-active { 
            display: flex; background: rgba(0,0,0,0.85); 
            backdrop-filter: blur(15px); pointer-events: auto;
        }
        
        .info-content {
            background: rgba(20, 29, 41, 0.95); width: 90%; max-width: 800px;
            border-radius: 24px; padding: 45px; border: 1px solid rgba(255,70,85,0.25);
            box-shadow: 0 0 60px rgba(0,0,0,1); color: #ece8e1;
            font-family: 'Rajdhani', sans-serif; position: relative;
            max-height: 85vh; overflow-y: auto;
            
            /* Initial State for Animation */
            transform: scale(0.85) translateY(30px);
            opacity: 0;
            filter: blur(15px);
            transition: 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        .info-modal.is-active .info-content {
            transform: scale(1) translateY(0);
            opacity: 1;
            filter: blur(0px);
        }
        .info-content h2 { color: var(--accent); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; }
        .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
        .info-section h3 { font-size: 1.2em; color: #fff; margin-top: 0; }
        .info-section p, .info-section li { font-family: 'Inter', sans-serif; font-size: 0.9em; line-height: 1.6; color: #aaa; }
        .info-close { position: absolute; top: 20px; right: 20px; cursor: pointer; color: #555; transition: 0.3s; }
        .info-close:hover { color: var(--accent); transform: rotate(90deg); }
        
        .info-btn { 
            width: 26px; height: 26px; border-radius: 50%;
            display: inline-flex; align-items: center; justify-content: center;
            background: radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.12), rgba(20, 26, 36, 0.95));
            border: 1px solid rgba(255, 255, 255, 0.14);
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45), inset 0 1px 1px rgba(255, 255, 255, 0.2);
            cursor: pointer;
            margin-left: 10px;
            vertical-align: middle;
            position: relative;
            outline: none;
            padding: 0;
            transition: all 0.28s cubic-bezier(0.2, 0.8, 0.2, 1);
        }
        .info-btn::before {
            content: '';
            position: absolute;
            inset: -2px;
            border-radius: 50%;
            background: radial-gradient(circle, var(--accent) 0%, transparent 70%);
            opacity: 0;
            filter: blur(4px);
            transition: opacity 0.3s ease;
            z-index: 0;
            pointer-events: none;
        }
        .info-btn-content {
            position: relative;
            z-index: 1;
            font-family: 'Rajdhani', sans-serif;
            font-size: 14px;
            font-weight: 800;
            color: rgba(255, 255, 255, 0.82);
            line-height: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
            transition: color 0.25s ease;
        }
        .info-btn:hover {
            transform: translateY(-2px) scale(1.08);
            border-color: var(--accent);
            box-shadow: 0 0 18px rgba(255, 70, 85, 0.5), inset 0 0 8px rgba(255, 70, 85, 0.3);
        }
        .info-btn:hover::before {
            opacity: 0.6;
        }
        .info-btn:hover .info-btn-content {
            color: #fff;
            text-shadow: 0 0 8px rgba(255, 255, 255, 0.8);
        }
        .info-btn:active {
            transform: translateY(0px) scale(0.96);
            box-shadow: 0 2px 8px rgba(255, 70, 85, 0.4);
        }

        /* Tactical Anti-AFK Question Mark Button (High-End Micro-Animation) */
        @keyframes afkHelpPulse {
            0%, 100% {
                box-shadow: 0 0 0 0 rgba(0, 245, 145, 0.4), inset 0 1px 2px rgba(255, 255, 255, 0.25);
                border-color: rgba(0, 245, 145, 0.35);
            }
            50% {
                box-shadow: 0 0 12px 2px rgba(0, 245, 145, 0.3), inset 0 1px 4px rgba(0, 245, 145, 0.2);
                border-color: rgba(0, 245, 145, 0.85);
            }
        }

        .afk-help-btn { 
            width: 22px; height: 22px; border-radius: 50%;
            display: inline-flex; align-items: center; justify-content: center;
            background: radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.12), rgba(20, 26, 36, 0.95));
            border: 1px solid rgba(0, 245, 145, 0.35);
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45), inset 0 1px 1px rgba(255, 255, 255, 0.2);
            cursor: pointer;
            margin-left: 5px;
            vertical-align: middle;
            position: relative;
            outline: none;
            padding: 0;
            transition: all 0.28s cubic-bezier(0.2, 0.8, 0.2, 1);
            animation: afkHelpPulse 3.5s ease-in-out infinite;
        }
        .afk-help-btn::before {
            content: '';
            position: absolute;
            inset: -2px;
            border-radius: 50%;
            background: radial-gradient(circle, var(--success) 0%, transparent 70%);
            opacity: 0;
            filter: blur(4px);
            transition: opacity 0.3s ease;
            z-index: 0;
            pointer-events: none;
        }
        .afk-help-btn-content {
            position: relative;
            z-index: 1;
            font-family: 'Rajdhani', sans-serif;
            font-size: 13px;
            font-weight: 800;
            color: rgba(255, 255, 255, 0.85);
            line-height: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
            transition: color 0.25s ease;
        }
        .afk-help-btn:hover {
            transform: translateY(-2px) scale(1.08);
            border-color: var(--success);
            box-shadow: 0 0 18px rgba(0, 245, 145, 0.5), inset 0 0 8px rgba(0, 245, 145, 0.3);
            animation: none;
        }
        .afk-help-btn:hover::before {
            opacity: 0.6;
        }
        .afk-help-btn:hover .afk-help-btn-content {
            color: #fff;
            text-shadow: 0 0 8px rgba(255, 255, 255, 0.8);
        }
        .afk-help-btn:active {
            transform: translateY(0px) scale(0.96);
            box-shadow: 0 2px 8px rgba(0, 245, 145, 0.4);
        }

        /* Anti-AFK Info Modal */
        #afk-modal .info-content {
            max-width: 650px;
            border: 1px solid rgba(0, 245, 145, 0.3);
            box-shadow: 0 0 60px rgba(0, 245, 145, 0.15), 0 0 100px rgba(0, 0, 0, 0.9);
        }

        #afk-modal h2 {
            color: var(--success);
            border-bottom: 1px solid rgba(0, 245, 145, 0.2);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .afk-feature-card {
            background: rgba(0, 245, 145, 0.03);
            border: 1px solid rgba(0, 245, 145, 0.12);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 16px;
        }

        .afk-feature-card h4 {
            margin: 0 0 8px 0;
            color: #00f591;
            font-size: 1.1em;
            letter-spacing: 1px;
            text-transform: uppercase;
        }

        .afk-feature-card p {
            margin: 0;
            font-family: 'Inter', sans-serif;
            font-size: 0.88em;
            line-height: 1.6;
            color: #bbb;
        }

        /* Signature Animation (v44.61) */
        @keyframes signaturePulse {
            0%, 100% { text-shadow: 0 0 5px var(--accent-glow); opacity: 0.8; }
            50% { text-shadow: 0 0 20px var(--accent), 0 0 30px var(--accent-glow); opacity: 1; }
        }
        .signature-glow {
            animation: signaturePulse 3s ease-in-out infinite;
            cursor: default;
        }

        /* Modern Tactical Discord Button (Subtle Pulse Synchronized with BY'KEPLERB) */
        @keyframes discordPulse {
            0%, 100% { 
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4), 0 0 4px rgba(88, 101, 242, 0.25);
                border-color: rgba(88, 101, 242, 0.28);
                opacity: 0.88; 
            }
            50% { 
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.5), 0 0 10px rgba(88, 101, 242, 0.5);
                border-color: rgba(88, 101, 242, 0.55);
                opacity: 1; 
            }
        }
        .discord-btn {
            display: inline-flex; align-items: center; justify-content: center;
            width: 23px; height: 23px; border-radius: 6px;
            background: linear-gradient(135deg, rgba(88, 101, 242, 0.12) 0%, rgba(15, 20, 28, 0.85) 100%);
            border: 1px solid rgba(88, 101, 242, 0.3);
            color: #5865F2; text-decoration: none;
            cursor: pointer; position: relative;
            vertical-align: middle;
            animation: discordPulse 3s ease-in-out infinite;
            transition: all 0.25s cubic-bezier(0.2, 0.8, 0.2, 1);
            box-sizing: border-box;
        }
        .discord-btn svg {
            width: 13px; height: 13px; fill: currentColor;
            display: block;
            transition: transform 0.25s ease;
        }
        .discord-btn:hover {
            color: #fff;
            background: linear-gradient(135deg, #5865F2 0%, #4752c4 100%);
            border-color: #7983f5;
            transform: translateY(-2px) scale(1.08);
            box-shadow: 0 0 14px rgba(88, 101, 242, 0.6) !important;
            opacity: 1;
        }
        .discord-btn:hover svg {
            transform: scale(1.1);
        }
        .discord-btn:active {
            transform: translateY(0px) scale(0.96);
            box-shadow: 0 2px 6px rgba(88, 101, 242, 0.4) !important;
        }

        /* Modern Tactical GitHub Button */
        @keyframes githubPulse {
            0%, 100% { 
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4), 0 0 4px rgba(255, 255, 255, 0.15);
                border-color: rgba(255, 255, 255, 0.2);
                opacity: 0.88; 
            }
            50% { 
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.5), 0 0 10px rgba(255, 255, 255, 0.35);
                border-color: rgba(255, 255, 255, 0.45);
                opacity: 1; 
            }
        }
        .github-btn {
            display: inline-flex; align-items: center; justify-content: center;
            width: 23px; height: 23px; border-radius: 6px;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(15, 20, 28, 0.85) 100%);
            border: 1px solid rgba(255, 255, 255, 0.22);
            color: rgba(255, 255, 255, 0.78); text-decoration: none;
            cursor: pointer; position: relative;
            vertical-align: middle;
            animation: githubPulse 3s ease-in-out infinite;
            transition: all 0.25s cubic-bezier(0.2, 0.8, 0.2, 1);
            box-sizing: border-box;
        }
        .github-btn svg {
            width: 13px; height: 13px; fill: currentColor;
            display: block;
            transition: transform 0.25s ease;
        }
        .github-btn:hover {
            color: #fff;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.25) 0%, rgba(35, 45, 60, 0.95) 100%);
            border-color: rgba(255, 255, 255, 0.6);
            transform: translateY(-2px) scale(1.08);
            box-shadow: 0 0 14px rgba(255, 255, 255, 0.45) !important;
            opacity: 1;
        }
        .github-btn:hover svg {
            transform: scale(1.1);
        }
        .github-btn:active {
            transform: translateY(0px) scale(0.96);
            box-shadow: 0 2px 6px rgba(255, 255, 255, 0.3) !important;
        }

        /* Red Neon VFX Trail (v44.75) */
        .vfx-particle {
            position: fixed; top: 0; left: 0; pointer-events: none; z-index: 9999;
            width: 6px; height: 6px; background: var(--accent);
            border-radius: 50%; box-shadow: 0 0 12px var(--accent), 0 0 20px var(--accent-glow);
            will-change: transform, opacity;
        }

        #notification-container { position: fixed; bottom: 20px; right: 20px; z-index: 10000; }
        .notification { 
            background: rgba(20, 29, 41, 0.95); backdrop-filter: blur(10px);
            border-right: 4px solid var(--accent); padding: 16px 24px; border-radius: 8px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5); margin-bottom: 10px; min-width: 300px;
            font-family: 'Rajdhani', sans-serif; animation: slideIn 0.4s ease forwards;
        }
        /* Player Skins Showcase Modal */
        .player-skins-modal {
            display: none; position: fixed; z-index: 2000; left: 0; top: 0;
            width: 100%; height: 100%; background: rgba(5, 8, 13, 0.85);
            backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
            align-items: center; justify-content: center;
            opacity: 0; transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            pointer-events: none; overscroll-behavior: contain;
        }
        .player-skins-modal.is-active {
            display: flex; opacity: 1; pointer-events: auto;
        }
        .skins-modal-box {
            background: linear-gradient(135deg, rgba(20, 29, 41, 0.98) 0%, rgba(11, 17, 25, 0.99) 100%);
            width: 95%; max-width: 1100px; max-height: 88vh;
            border-radius: 20px; border: 1px solid rgba(255, 70, 85, 0.35);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.8), 0 0 40px rgba(255, 70, 85, 0.15);
            color: #ece8e1; font-family: 'Rajdhani', sans-serif;
            position: relative; display: flex; flex-direction: column;
            overflow: hidden;
            transform: scale(0.92) translateY(20px);
            transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        .player-skins-modal.is-active .skins-modal-box {
            transform: scale(1) translateY(0);
        }
        .skins-modal-header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 22px 28px; background: rgba(10, 15, 23, 0.7);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            position: relative;
        }
        .skins-modal-header::after {
            content: ''; position: absolute; bottom: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent), transparent);
        }
        .modal-player-profile {
            display: flex; align-items: center; gap: 18px;
        }
        .modal-agent-avatar-wrap {
            position: relative; width: 62px; height: 62px;
            border-radius: 14px; overflow: hidden;
            background: rgba(255, 70, 85, 0.1);
            border: 2px solid rgba(255, 70, 85, 0.4);
            box-shadow: 0 0 20px rgba(255, 70, 85, 0.25);
            flex-shrink: 0;
        }
        .modal-agent-avatar-wrap img.avatar {
            width: 100%; height: 100%; object-fit: cover;
        }
        .modal-rank-corner {
            position: absolute; bottom: -2px; right: -2px; width: 26px; height: 26px;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.8));
        }
        .modal-player-meta h2 {
            margin: 0; font-size: 1.8em; font-weight: 700; letter-spacing: 1.5px;
            display: flex; align-items: center; gap: 10px;
        }
        .modal-player-meta h2 span.tag {
            font-size: 0.65em; color: rgba(255,255,255,0.45); font-weight: 500;
        }
        .modal-badges-row {
            display: flex; align-items: center; gap: 8px; margin-top: 6px; flex-wrap: wrap;
        }
        .m-badge {
            font-size: 0.85em; font-weight: 800; padding: 4px 10px 4px 8px; border-radius: 6px;
            letter-spacing: 0.8px; text-transform: uppercase;
            display: inline-flex; align-items: center; gap: 6px; line-height: 1;
        }
        .badge-rank-icon {
            width: 18px; height: 18px; min-width: 18px; min-height: 18px;
            object-fit: contain; filter: drop-shadow(0 0 4px rgba(0,0,0,0.7));
            flex-shrink: 0;
        }
        .m-badge-rank { background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.15); color: #fff; }
        .m-badge-level { background: rgba(0, 245, 145, 0.1); border: 1px solid rgba(0, 245, 145, 0.3); color: var(--success); }
        .m-badge-premium { background: rgba(255, 177, 0, 0.15); border: 1px solid rgba(255, 177, 0, 0.4); color: #ffb100; box-shadow: 0 0 10px rgba(255, 177, 0, 0.2); }
        .m-badge-party { background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.3); color: #38bdf8; }

        .skins-modal-close {
            background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1);
            color: #ccc; width: 36px; height: 36px; border-radius: 50%;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
            font-size: 20px; font-weight: 700; transition: 0.25s ease;
        }
        .skins-modal-close:hover {
            background: var(--accent); color: #fff; border-color: var(--accent);
            transform: rotate(90deg) scale(1.1); box-shadow: 0 0 15px var(--accent-glow);
        }

        .skins-modal-tabs {
            display: flex; gap: 10px; padding: 14px 28px; background: rgba(14, 21, 30, 0.75);
            border-bottom: 1px solid rgba(255, 255, 255, 0.06); overflow-x: auto;
            scrollbar-width: none; flex-wrap: wrap; align-items: center;
        }
        .skins-modal-tabs::-webkit-scrollbar { display: none; }
        .skin-tab-btn {
            background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.09);
            color: #aaa; padding: 8px 18px; border-radius: 8px; cursor: pointer;
            font-family: 'Rajdhani', sans-serif; font-weight: 700; font-size: 0.9em;
            letter-spacing: 1px; transition: 0.2s ease; white-space: nowrap;
            text-transform: uppercase; display: inline-flex; align-items: center; justify-content: center;
        }
        .skin-tab-btn:hover {
            background: rgba(255, 70, 85, 0.12); color: #fff; border-color: rgba(255, 70, 85, 0.4);
        }
        .skin-tab-btn.active {
            background: var(--accent); color: #fff; border-color: var(--accent);
            box-shadow: 0 0 15px var(--accent-glow);
        }

        .skins-modal-body {
            padding: 24px 28px; overflow-y: auto; flex: 1;
            overscroll-behavior: contain; touch-action: pan-y;
            scrollbar-width: thin; scrollbar-color: rgba(255, 70, 85, 0.3) rgba(0,0,0,0.2);
        }
        .skins-modal-body::-webkit-scrollbar { width: 6px; }
        .skins-modal-body::-webkit-scrollbar-thumb { background: rgba(255, 70, 85, 0.4); border-radius: 4px; }

        .weapon-cards-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(235px, 1fr));
            gap: 16px;
        }
        .weapon-card {
            background: rgba(255, 255, 255, 0.025); border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 14px; padding: 14px 16px; position: relative;
            display: flex; flex-direction: column; justify-content: space-between;
            min-height: 145px; transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            overflow: hidden;
        }
        .weapon-card::before {
            content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%;
            background: rgba(255, 255, 255, 0.15); transition: 0.25s ease;
        }
        .weapon-card:hover {
            transform: translateY(-4px); background: rgba(255, 255, 255, 0.05);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
        }
        .weapon-card.is-knife {
            border-color: rgba(255, 177, 0, 0.4);
            background: linear-gradient(135deg, rgba(255, 177, 0, 0.06) 0%, rgba(20, 29, 41, 0.4) 100%);
        }
        .weapon-card.is-knife::before {
            background: #ffb100; box-shadow: 0 0 10px #ffb100;
        }
        .weapon-card.is-premium {
            border-color: rgba(0, 245, 145, 0.35);
            background: linear-gradient(135deg, rgba(0, 245, 145, 0.04) 0%, rgba(20, 29, 41, 0.4) 100%);
        }
        .weapon-card.is-premium::before {
            background: var(--success); box-shadow: 0 0 10px var(--success);
        }
        .weapon-card-top {
            display: flex; justify-content: space-between; align-items: center;
        }
        .w-name-badge {
            font-size: 0.85em; font-weight: 700; color: #aaa; letter-spacing: 1px;
            text-transform: uppercase;
        }
        .w-status-badge {
            font-size: 0.7em; font-weight: 700; padding: 2px 7px; border-radius: 4px;
            letter-spacing: 0.6px;
        }
        .badge-prem { background: rgba(0, 245, 145, 0.15); color: var(--success); border: 1px solid rgba(0, 245, 145, 0.3); }
        .badge-knife { background: rgba(255, 177, 0, 0.18); color: #ffb100; border: 1px solid rgba(255, 177, 0, 0.4); }
        .badge-std { background: rgba(255, 255, 255, 0.05); color: #777; }

        .weapon-card-img-wrap {
            height: 65px; display: flex; align-items: center; justify-content: center;
            margin: 10px 0; position: relative;
        }
        .weapon-card-img-wrap img {
            max-width: 90%; max-height: 55px; object-fit: contain;
            filter: drop-shadow(0 4px 10px rgba(0,0,0,0.6));
            transition: transform 0.3s ease;
        }
        .weapon-card:hover .weapon-card-img-wrap img {
            transform: scale(1.08);
        }
        .weapon-card-bottom {
            border-top: 1px solid rgba(255, 255, 255, 0.06); padding-top: 8px;
        }
        .skin-title {
            font-size: 1.05em; font-weight: 700; color: #fff; letter-spacing: 0.8px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .skin-category-sub {
            font-size: 0.75em; color: rgba(255,255,255,0.4); font-family: 'Inter', sans-serif;
            margin-top: 2px;
        }

        /* Player Row Inspect Pill & Hover */
        .player-row {
            cursor: pointer;
            position: relative;
            transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s ease, border-color 0.2s ease;
        }
        .player-row:hover {
            transform: translateY(-2px);
            border-color: rgba(255, 70, 85, 0.45) !important;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.5), 0 0 20px rgba(255, 70, 85, 0.15);
        }
        .inspect-hint {
            display: inline-flex; align-items: center; gap: 5px;
            font-size: 0.7em; font-weight: 700; letter-spacing: 1px;
            color: rgba(255,255,255,0.4); padding: 3px 8px; border-radius: 4px;
            background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);
            margin-left: 8px; transition: 0.2s ease;
        }
        .player-row:hover .inspect-hint {
            color: #fff; background: rgba(255, 70, 85, 0.2); border-color: rgba(255, 70, 85, 0.4);
        }
    </style>
</head>
<body>
    <div id="notification-container"></div>
    <div id="info-modal" class="info-modal" onclick="if(event.target == this) toggleModal(false)">
        <div class="info-content">
            <div class="info-close" onclick="toggleModal(false)">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </div>
            <h2>PROJECT INFORMATION // PROJE BİLGİSİ</h2>
            <div class="info-grid">
                <!-- English -->
                <div class="info-section">
                    <h3>[EN] About Project</h3>
                    <p>Valo Locker is an elite, tactical dashboard designed for high-performance players who want to gain match intelligence instantly.</p>
                    <p><strong>Core Features:</strong></p>
                    <ul>
                        <li>Automated Insta-Locking system</li>
                        <li>Pro-active Anti-AFK movements</li>
                        <li>Real-time Rank & KP intelligence</li>
                        <li>Deep Skin inventory analysis</li>
                        <li>Party composition detection</li>
                    </ul>
                    <p style="color: var(--success); font-weight: bold;">[#] This project is fully Open Source and developed for educational transparency.</p>
                    <p style="color: var(--accent); font-weight: bold;">[!] This entire project, including UI design, logic, and animations, was created using Advanced Artificial Intelligence.</p>
                </div>
                <!-- Turkish -->
                <div class="info-section">
                    <h3>[TR] Proje Hakkında</h3>
                    <p>Valo Locker, maç istihbaratını anında elde etmek isteyen yüksek performanslı oyuncular için tasarlanmış elit bir taktiksel paneldir.</p>
                    <p><strong>Ana Özellikler:</strong></p>
                    <ul>
                        <li>Otomatik Ajan Kilitleme sistemi</li>
                        <li>Pro-aktif Anti-AFK mekanizması</li>
                        <li>Gerçek zamanlı Rütbe ve KP analizi</li>
                        <li>Derinlemesine Skin envanter taraması</li>
                        <li>Parti/Grup oluşumu tespiti</li>
                    </ul>
                    <p style="color: var(--success); font-weight: bold;">[#] Bu proje tamamen Açık Kaynaklıdır ve teknik şeffaflık amacıyla geliştirilmiştir.</p>
                    <p style="color: var(--accent); font-weight: bold;">[!] Bu projenin arayüz tasarımı, mantık yapısı ve animasyonları dahil TAMAMI Yapay Zeka kullanılarak oluşturulmuştur.</p>
                </div>
            </div>
        </div>
    </div>

    <!-- ANTI-AFK EXPLANATION MODAL -->
    <div id="afk-modal" class="info-modal" onclick="if(event.target == this) toggleAfkModal(false)">
        <div class="info-content">
            <div class="info-close" onclick="toggleAfkModal(false)">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </div>
            <h2>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00f591" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg>
                <span data-i18n="afk_modal_title">ANTI-AFK SİSTEMİ BİLGİLENDİRMESİ</span>
            </h2>
            
            <div class="afk-feature-card">
                <h4 data-i18n="afk_card1_title">🛡️ NASIL ÇALIŞIR?</h4>
                <p data-i18n="afk_card1_desc">Siz bilgisayar başından ayrıldığınızda veya oyunu simge durumuna küçülttüğünüzde, arka planda güvenli Windows API çağrıları üzerinden periyodik ve doğal insan ritminde tuş vuruşları simüle eder. Böylece Valorant'ın AFK / Hareketsizlik ceza sistemine takılmazsınız.</p>
            </div>

            <div class="afk-feature-card">
                <h4 data-i18n="afk_card2_title">⚙️ ÖNE ÇIKAN ÖZELLİKLER</h4>
                <p data-i18n="afk_card2_desc"><strong>• Arka Planda Çalışma:</strong> Oyun odakta olmasa dahi kesintisiz hareket sağlar.<br>
                <strong>• Akıllı Rastgele Aralıklar:</strong> Robotik tespiti engellemek için tuş basma aralıkları rastgele sürelerle değişkenlik gösterir.<br>
                <strong>• Düşük Kaynak Tüketimi:</strong> %0 işlemci yükü ile arka planda sessiz çalışır.</p>
            </div>

            <div class="afk-feature-card" style="margin-bottom:0; border-color:rgba(255,184,0,0.3); background:rgba(255,184,0,0.04);">
                <h4 style="color:#ffb800;" data-i18n="afk_card3_title">⚠️ KULLANIM TAVSİYESİ</h4>
                <p data-i18n="afk_card3_desc">Özellikle Ajan Seçim Ekranı beklerken, tur aralarında kısa süreli mola verirken veya ölüm maçı / derecesiz modlarda tuvalet/su molası verirken açmanız önerilir. İhtiyacınız bittiğinde butondan kapatabilirsiniz.</p>
            </div>
        </div>
    </div>
    <!-- PLAYER WEAPONS & SKINS SHOWCASE MODAL (v45.2) -->
    <div id="player-skins-modal" class="player-skins-modal" onclick="if(event.target == this) closePlayerModal()">
        <div class="skins-modal-box">
            <div class="skins-modal-header">
                <div class="modal-player-profile">
                    <div class="modal-agent-avatar-wrap">
                        <img id="pm-agent-img" class="avatar" src="" alt="Agent">
                        <img id="pm-rank-img" class="modal-rank-corner" src="" alt="Rank">
                    </div>
                    <div class="modal-player-meta">
                        <h2>
                            <span id="pm-player-name">Player</span>
                            <span id="pm-player-tag" class="tag">#TAG</span>
                        </h2>
                        <div class="modal-badges-row">
                            <span class="m-badge m-badge-rank" id="pm-rank-badge">Unranked</span>
                            <span class="m-badge m-badge-peak" id="pm-peak-badge" style="display:none; color:#f59e0b; border-color:rgba(245,158,11,0.4); background:rgba(245,158,11,0.12);">PEAK</span>
                            <span class="m-badge m-badge-level" id="pm-level-badge">LVL -</span>
                            <span class="m-badge m-badge-party" id="pm-party-badge">SOLO</span>
                            <span class="m-badge m-badge-premium" id="pm-prem-badge">★ 0 ÖZEL SKİN</span>
                        </div>
                    </div>
                </div>
                <button class="skins-modal-close" onclick="closePlayerModal()" title="Kapat (ESC)">&times;</button>
            </div>

            <div class="skins-modal-body">
                <div class="weapon-cards-grid" id="pm-weapons-grid">
                    <!-- Dinamik olarak silah kartları eklenecek -->
                </div>
            </div>
        </div>
    </div>
    <div class="container">
        <!-- Header -->
        <header class="glass-panel">
            <div class="header-logo-container">
                <img src="data:image/png;base64,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" alt="KepsLocker Logo" class="header-logo" onclick="window.location.reload()" title="Sayfayı Yenile (F5) / Refresh Page">
                <div>
                    <h1>VALORANT <span style="color:var(--accent)">INSTALOCKER</span> <span class="version-badge">PREMIUM v1</span><button type="button" class="info-btn" onclick="toggleModal(true)" title="Proje Bilgisi / Project Information" aria-label="Proje Bilgisi"><span class="info-btn-content">?</span></button></h1>
                    <div style="font-size:1em; color:#888; margin-top:5px; font-family:'Rajdhani', sans-serif; font-weight:600; letter-spacing:1px; display:flex; align-items:center; gap:10px;">
                        DARKSIDE ELITE GAMING DASHBOARD
                        <span style="width:4px; height:4px; background:rgba(255,255,255,0.1); border-radius:50%;"></span>
                        <span class="signature-glow" style="color:var(--accent); font-weight:800; letter-spacing:2px; font-size:0.9em;">BY'KEPLERB</span>
                        <a href="https://discord.gg/93DSqGVXa2" target="_blank" rel="noopener noreferrer" class="discord-btn" title="Discord Sunucumuza Katıl" aria-label="Discord">
                            <svg viewBox="0 0 24 24">
                                <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.893.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
                            </svg>
                        </a>
                        <a href="https://github.com/Keplorions/Valorant-InstaLocker" target="_blank" rel="noopener noreferrer" class="github-btn" title="GitHub Depomuzu Ziyaret Et" aria-label="GitHub">
                            <svg viewBox="0 0 24 24">
                                <path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
                            </svg>
                        </a>
                    </div>
                </div>
            </div>
            <div class="status-pill">
                <div id="map-badge" style="background:rgba(255,70,85,0.15); padding:4px 15px; border-radius:20px; border:1px solid rgba(255,70,85,0.3); display:none; align-items:center;">
                    <span style="color:var(--accent); margin-right:8px; font-weight:900; font-size:0.8em; letter-spacing:1px;">MAP //</span> 
                    <span id="current-map" style="color:#fff; font-weight:bold;">-</span>
                </div>
                <div class="lang-dropdown" style="margin-right:15px;">
                    <div class="lang-dropdown-btn">
                        <img id="current-lang-flag" src="https://flagcdn.com/w40/gb.png" alt="Lang">
                        <span id="current-lang-label">EN</span>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px; height:14px; opacity:0.5; margin-left:2px;">
                            <polyline points="6 9 12 15 18 9"/>
                        </svg>
                    </div>
                    <div class="lang-dropdown-menu">
                        <div class="lang-option" onclick="setLanguage('tr')" id="lang-opt-tr">
                            <img src="https://flagcdn.com/w40/tr.png" alt="TR">
                            <span>TR</span>
                        </div>
                        <div class="lang-option" onclick="setLanguage('en')" id="lang-opt-en">
                            <img src="https://flagcdn.com/w40/gb.png" alt="EN">
                            <span>EN</span>
                        </div>
                    </div>
                </div>
                <div id="conn-ind" class="indicator"></div>
                <span id="connection-status" style="color:#aaa;">BEKLENİYOR</span>
                <span id="match-timer" style="background:rgba(255,255,255,0.1); padding:4px 12px; border-radius:6px; color:#fff; font-size:1.1em; letter-spacing:1px;">--:--</span>
            </div>
        </header>

        <div class="grid">
            <!-- LEFT: Controls -->
            <div class="glass-panel">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
                    <h2 data-i18n="agent_selection" style="margin:0; font-family:'Rajdhani', sans-serif; text-transform:uppercase; letter-spacing:1px; border-left:4px solid var(--accent); padding-left:12px;">AJAN SEÇİMİ</h2>
                    <div class="toggle-container">
                        <div style="display:flex; align-items:center; gap:5px;">
                            <span style="font-size:0.75em; font-weight:800; color:#aaa; letter-spacing:1px; font-family:'Rajdhani', sans-serif;">ANTI-AFK</span>
                            <button type="button" class="info-btn" onclick="toggleAfkModal(true)" title="Anti-AFK Nedir? Nasıl Çalışır?" aria-label="Anti-AFK Bilgisi" style="margin-left:0; width:22px; height:22px;"><span class="info-btn-content" style="font-size:12px;">?</span></button>
                        </div>
                        <label class="toggle-switch" title="Anti-AFK Aç / Kapat">
                            <input type="checkbox" id="afk-toggle" onchange="toggleAfk(this.checked)">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                </div>
                
                <div id="agent-grid">
                    <!-- Populated by JS -->
                </div>
                
                <button class="big-btn" id="lock-btn" onclick="startLocking()" data-i18n="btn_lock">KİLİTLE</button>
                <div id="lock-status" style="text-align:center; margin-top:15px; font-size:0.9em; min-height:40px; display:flex; flex-direction:column; align-items:center; justify-content:center;">
                    <span data-i18n="select_agent_prompt" style="color:#555; font-weight:600;">Lütfen bir ajan seçin</span>
                </div>
            </div>

            <!-- RIGHT: Match Info -->
            <div>
                <!-- ALLIES -->
                <div class="team-section">
                    <div class="team-header team-ally">
                        <div style="display:flex; align-items:center;">
                            <span data-i18n="ally_team">ALLY TEAM</span>
                            <div id="ally-summary" style="margin-left:15px; font-size:0.5em; letter-spacing:1px; color:#aaa;"></div>
                        </div>
                    </div>
                    <div id="ally-container">
                        <!-- Cards will be injected here -->
                    </div>
                </div>

                <!-- ENEMIES -->
                <div class="team-section">
                    <div class="team-header team-enemy">
                        <div style="display:flex; align-items:center;">
                            <span data-i18n="enemy_squad">ENEMY SQUAD</span>
                            <div id="enemy-summary" style="margin-left:15px; font-size:0.5em; letter-spacing:1px; color:#aaa;"></div>
                        </div>
                    </div>
                    <div id="enemy-container">
                        <!-- Cards will be injected here -->
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script>
        // Zero-Dependency DOM Helper / jQuery Fallback (Offline / Brave Shields Safe)
        (function() {
            if (typeof window.$ === 'undefined' || typeof window.jQuery === 'undefined') {
                function DomCollection(elements) {
                    this.elements = elements || [];
                    this.length = this.elements.length;
                    for (let i = 0; i < this.elements.length; i++) this[i] = this.elements[i];
                }
                DomCollection.prototype = {
                    each: function(cb) { this.elements.forEach((el, i) => cb.call(el, i, el)); return this; },
                    text: function(txt) {
                        if (txt === undefined) return this.elements[0] ? this.elements[0].textContent : '';
                        this.elements.forEach(el => el.textContent = txt); return this;
                    },
                    html: function(h) {
                        if (h === undefined) return this.elements[0] ? this.elements[0].innerHTML : '';
                        this.elements.forEach(el => el.innerHTML = h); return this;
                    },
                    attr: function(k, v) {
                        if (v === undefined) return this.elements[0] ? this.elements[0].getAttribute(k) : null;
                        this.elements.forEach(el => { if (k === 'src') el.src = v; else el.setAttribute(k, v); }); return this;
                    },
                    data: function(k) {
                        return this.elements[0] ? this.elements[0].getAttribute('data-' + k) : undefined;
                    },
                    addClass: function(c) { this.elements.forEach(el => el.classList.add(c)); return this; },
                    removeClass: function(c) { this.elements.forEach(el => el.classList.remove(c)); return this; },
                    toggleClass: function(c, force) {
                        this.elements.forEach(el => {
                            if (force !== undefined) el.classList.toggle(c, force);
                            else el.classList.toggle(c);
                        });
                        return this;
                    },
                    css: function(prop, val) {
                        if (val === undefined) {
                            if (typeof prop === 'object') {
                                this.elements.forEach(el => Object.assign(el.style, prop));
                                return this;
                            }
                            return this.elements[0] ? this.elements[0].style[prop] : '';
                        }
                        this.elements.forEach(el => el.style[prop] = val);
                        return this;
                    },
                    empty: function() { this.elements.forEach(el => el.innerHTML = ''); return this; },
                    append: function(content) {
                        this.elements.forEach(el => {
                            if (typeof content === 'string') el.insertAdjacentHTML('beforeend', content);
                            else if (content instanceof DomCollection) content.elements.forEach(c => el.appendChild(c));
                            else if (content && content.nodeType) el.appendChild(content);
                        });
                        return this;
                    },
                    show: function() { this.elements.forEach(el => el.style.display = ''); return this; },
                    hide: function() { this.elements.forEach(el => el.style.display = 'none'); return this; },
                    on: function(evt, selector, handler) {
                        if (typeof selector === 'function') {
                            handler = selector;
                            this.elements.forEach(el => el.addEventListener(evt, handler));
                        } else {
                            this.elements.forEach(el => el.addEventListener(evt, function(e) {
                                const t = e.target.closest(selector);
                                if (t && el.contains(t)) handler.call(t, e);
                            }));
                        }
                        return this;
                    }
                };
                window.$ = window.jQuery = function(selector) {
                    if (!selector) return new DomCollection([]);
                    if (typeof selector === 'function') {
                        if (document.readyState === 'loading') {
                            document.addEventListener('DOMContentLoaded', selector);
                        } else {
                            selector();
                        }
                        return;
                    }
                    if (selector === document) return new DomCollection([document]);
                    if (selector === window) return new DomCollection([window]);
                    if (selector.nodeType) return new DomCollection([selector]);
                    if (typeof selector === 'string') {
                        if (selector.trim().startsWith('<')) {
                            const temp = document.createElement('div');
                            temp.innerHTML = selector.trim();
                            return new DomCollection(Array.from(temp.children));
                        }
                        return new DomCollection(Array.from(document.querySelectorAll(selector)));
                    }
                    if (Array.isArray(selector) || selector instanceof NodeList || selector instanceof HTMLCollection) {
                        return new DomCollection(Array.from(selector));
                    }
                    return new DomCollection([]);
                };
                window.$.get = function(url, cb) {
                    fetch(url).then(r => r.json()).then(cb).catch(e => console.warn('Fetch error:', e));
                };
            }
        })();

        const LANG_DATA = {
            'tr': {
                'agent_selection': 'AJAN SEÇİMİ',
                'btn_lock': 'KİLİTLE',
                'btn_locked': 'KİLİTLENDİ',
                'select_agent_prompt': 'Lütfen bir ajan seçin',
                'ally_team': 'DOST EKİP',
                'enemy_squad': 'RAKİP EKİP',
                'system_active': 'SİSTEM AKTİF',
                'waiting_val': 'VALORANT BEKLENİYOR',
                'scanning': 'SİSTEM TARANIYOR',
                'waiting_data': 'MEVCUT VERİ BEKLENİYOR...',
                'ready_to_lock': 'hazır!',
                'locking': 'KİLİTLENİYOR...',
                'at_lock_active': 'için otomatik kilitleme aktif!',
                'conn_error': 'Sistem bağlantı hatası!',
                'afk_on': 'Anti-AFK Aktif',
                'afk_off': 'Anti-AFK Kapatıldı',
                'lock_refresh_note': 'Not: Her oyundan sonra siteyi yenileyiniz (F5 atınız)',
                'stealth_offline': 'GÖRÜNMEZ MOD',
                'badge_standard': 'STANDART',
                'badge_knife': '★ BIÇAK',
                'badge_premium': '★ ÖZEL SKİN',
                'special_skins': 'ÖZEL SKİN',
                'party_group': 'GRUP',
                'party_solo': 'SOLO',
                'peak_rank': 'ZİRVE',
                'map': 'HARİTA',
                'unknown': 'Bilinmiyor',
                'hidden_player': 'Gizli',
                'hidden_level': 'Gizli',
                'afk_modal_title': 'ANTI-AFK SİSTEMİ BİLGİLENDİRMESİ',
                'afk_card1_title': '🛡️ NASIL ÇALIŞIR?',
                "afk_card1_desc": "Bilgisayar başından ayrıldığınızda veya oyunu simge durumuna küçülttüğünüzde, arka planda güvenli Windows API çağrıları üzerinden periyodik ve doğal insan ritminde tuş vuruşları simüle eder. Böylece Valorant AFK ceza sistemine takılmazsınız.",
                'afk_card2_title': '⚙️ ÖNE ÇIKAN ÖZELLİKLER',
                'afk_card2_desc': '• Arka Planda Çalışma: Oyun odakta olmasa dahi kesintisiz hareket sağlar.<br>• Akıllı Rastgele Aralıklar: Robotik tespiti engellemek için tuş basma aralıkları rastgele sürelerle değişkenlik gösterir.<br>• Düşük Kaynak Tüketimi: %0 işlemci yükü ile arka planda sessiz çalışır.',
                'afk_card3_title': '⚠️ KULLANIM TAVSİYESİ',
                'afk_card3_desc': 'Özellikle Ajan Seçim Ekranı beklerken, tur aralarında kısa süreli mola verirken veya ölüm maçı / derecesiz modlarda mola verirken açmanız önerilir. İhtiyacınız bittiğinde butondan kapatabilirsiniz.',
                'phases': {
                    'WAITING': 'BEKLENİYOR',
                    'PREGAME': 'KARAKTER SEÇİMİ',
                    'INGAME': 'OYUN OYNANIYOR',
                    'MATCH_END': 'MAÇ SONU'
                }
            },
            'en': {
                'agent_selection': 'AGENT SELECTION',
                'btn_lock': 'LOCK AGENT',
                'btn_locked': 'LOCKED',
                'select_agent_prompt': 'Please select an agent',
                'ally_team': 'ALLY TEAM',
                'enemy_squad': 'ENEMY SQUAD',
                'system_active': 'SYSTEM ACTIVE',
                'waiting_val': 'WAITING FOR VALORANT',
                'scanning': 'SCANNING SYSTEM',
                'waiting_data': 'WAITING FOR MATCH DATA...',
                'ready_to_lock': 'ready!',
                'locking': 'LOCKING...',
                'at_lock_active': 'auto-lock is active!',
                'conn_error': 'System connection error!',
                'afk_on': 'Anti-AFK Active',
                'afk_off': 'Anti-AFK Disabled',
                'lock_refresh_note': 'Note: Please refresh the site after each game (Press F5)',
                'stealth_offline': 'APPEAR OFFLINE',
                'badge_standard': 'STANDARD',
                'badge_knife': '★ MELEE',
                'badge_premium': '★ SPECIAL SKIN',
                'special_skins': 'SPECIAL SKIN',
                'party_group': 'PARTY',
                'party_solo': 'SOLO',
                'peak_rank': 'PEAK',
                'map': 'MAP',
                'unknown': 'Unknown',
                'hidden_player': 'Hidden',
                'hidden_level': 'Hidden',
                'afk_modal_title': 'ANTI-AFK SYSTEM OVERVIEW',
                'afk_card1_title': '🛡️ HOW DOES IT WORK?',
                'afk_card1_desc': 'When you step away from your PC or minimize the game, the system simulates periodic, human-like keystrokes via native Windows APIs in the background. This prevents Valorant from triggering idle/AFK penalties.',
                'afk_card2_title': '⚙️ KEY ADVANTAGES',
                'afk_card2_desc': '• Background Mode: Works even if Valorant is minimized or not in focus.<br>• Human Randomized Intervals: Randomized key intervals eliminate robotic detection patterns.<br>• Ultra Lightweight: Consumes 0% noticeable CPU and operates silently.',
                'afk_card3_title': '⚠️ BEST PRACTICES',
                'afk_card3_desc': 'Recommended when queuing, during buy phases, or during short breaks in unrated/deathmatch lobbies. Toggle off once you return to your keyboard.',
                'phases': {
                    'WAITING': 'WAITING',
                    'PREGAME': 'CHARACTER SELECTION',
                    'INGAME': 'IN PROGRESS',
                    'MATCH_END': 'MATCH END'
                }
            }
        };

        let currentLang = localStorage.getItem('valolocker_lang') || 'en';
        let selectedAgent = null;
        let isAfkActive = false;
        let lastData = null;
        let AGENT_GROUPS = {};
        let CURRENT_MODAL_PLAYER = null;
        let CURRENT_MODAL_FILTER = 'all';

        function t(key) {
            return LANG_DATA[currentLang][key] || key;
        }

        function setLanguage(lang) {
            currentLang = lang;
            localStorage.setItem('valolocker_lang', lang);
            // Update dropdown label, flag and active state
            $('#current-lang-label').text(lang.toUpperCase());
            const flagUrl = lang === 'tr' ? 'https://flagcdn.com/w40/tr.png' : 'https://flagcdn.com/w40/gb.png';
            $('#current-lang-flag').attr('src', flagUrl);
            
            $('.lang-option').removeClass('active');
            $(`#lang-opt-${lang}`).addClass('active');
            $('.lang-dropdown').removeClass('open'); // Close dropdown after selection
            updateUIStrings();
        }

        // Toggle dropdown on click
        $(document).on('click', '.lang-dropdown-btn', function(e) {
            e.stopPropagation();
            $('.lang-dropdown').toggleClass('open');
        });
        // Close dropdown when clicking outside
        $(document).on('click', function() {
            $('.lang-dropdown').removeClass('open');
        });

        function updateUIStrings() {
            $('[data-i18n]').each(function() {
                const key = $(this).data('i18n');
                const val = t(key);
                if (typeof val === 'string' && val.includes('<') && val.includes('>')) {
                    $(this).html(val);
                } else {
                    $(this).text(val);
                }
            });
            // Re-render components that use translations
            if (lastData && typeof updateDataFromObj === 'function') {
                updateDataFromObj(lastData);
            }
            if (CURRENT_MODAL_PLAYER && typeof openPlayerModal === 'function') {
                openPlayerModal(CURRENT_MODAL_PLAYER.puuid);
            }
        }

        // Red Neon VFX Trail Logic (Safe DOM Ready)
        const particles = [];
        const particleCount = 20;
        let mX = 0, mY = 0;

        function initVFX() {
            try {
                for (let i = 0; i < particleCount; i++) {
                    const p = document.createElement('div');
                    p.className = 'vfx-particle';
                    p.style.opacity = '0';
                    document.body.appendChild(p);
                    particles.push({
                        el: p,
                        x: 0, y: 0,
                        targetX: 0, targetY: 0
                    });
                }

                document.addEventListener('mousemove', (e) => {
                    mX = e.clientX;
                    mY = e.clientY;
                });

                function animateVFX() {
                    let curX = mX + 15;
                    let curY = mY + 22;

                    particles.forEach((p, index) => {
                        p.x += (curX - p.x) * 0.20;
                        p.y += (curY - p.y) * 0.20;
                        
                        const size = (1 - index / particleCount) * 6;
                        const opacity = (1 - index / particleCount) * 0.8;
                        
                        p.el.style.transform = `translate3d(${p.x - size/2}px, ${p.y - size/2}px, 0)`;
                        p.el.style.width = `${size}px`;
                        p.el.style.height = `${size}px`;
                        p.el.style.opacity = opacity;
                        
                        curX = p.x;
                        curY = p.y;
                    });
                    requestAnimationFrame(animateVFX);
                }
                animateVFX();
            } catch(e) { console.warn("VFX init skipped:", e); }
        }

        function toggleModal(show) {
            const modal = document.getElementById('info-modal');
            if(!modal) return;
            if(show) {
                modal.style.display = 'flex';
                void modal.offsetWidth;
                modal.classList.add('is-active');
            } else {
                modal.classList.remove('is-active');
                setTimeout(() => {
                    if (!modal.classList.contains('is-active')) {
                        modal.style.display = 'none';
                    }
                }, 500);
            }
        }

        function toggleAfkModal(show) {
            const modal = document.getElementById('afk-modal');
            if(!modal) return;
            if(show) {
                modal.style.display = 'flex';
                void modal.offsetWidth;
                modal.classList.add('is-active');
            } else {
                modal.classList.remove('is-active');
                setTimeout(() => {
                    if (!modal.classList.contains('is-active')) {
                        modal.style.display = 'none';
                    }
                }, 500);
            }
        }

        console.log("VALO LOCKER PREMIUM v44.0 INITIALIZED");

        function showNotification(msg, type = 'info') {
            const container = document.getElementById('notification-container');
            if (!container) return;
            const notif = document.createElement('div');
            notif.className = `notification ${type}`;
            notif.innerHTML = `<span>${msg}</span>`;
            container.appendChild(notif);
            setTimeout(() => {
                notif.style.opacity = '0';
                setTimeout(() => notif.remove(), 500);
            }, 5000);
        }
        
        async function fetchAgents() {
            try {
                const res = await fetch('/api/agents');
                if (res.ok) {
                    const data = await res.json();
                    if (data && Object.keys(data).length > 0) {
                        AGENT_GROUPS = data;
                        renderOriginalGrid();
                        return;
                    }
                }
            } catch(e) {
                console.warn("Error fetching agents:", e);
            }
            setTimeout(fetchAgents, 1500);
        }

        function renderOriginalGrid() {
            const grid = document.getElementById('agent-grid');
            if (!grid) return;
            grid.innerHTML = '';
            
            // Tüm ajanları tek bir listede topla ve alfabetik sırala
            let allAgents = [];
            Object.values(AGENT_GROUPS).forEach(group => {
                if (Array.isArray(group)) {
                    allAgents = allAgents.concat(group);
                }
            });
            
            if (allAgents.length === 0) return;

            const uniqueMap = new Map();
            allAgents.forEach(a => {
                if (a && a.name) {
                    const normKey = a.name.trim().toLowerCase();
                    if (!uniqueMap.has(normKey)) {
                        uniqueMap.set(normKey, a);
                    }
                }
            });

            Array.from(uniqueMap.values()).sort((a,b) => a.name.localeCompare(b.name)).forEach(agent => {
                const btn = document.createElement('div');
                btn.className = `agent-btn ${selectedAgent === agent.name ? 'active' : ''}`;
                btn.dataset.name = agent.name;
                btn.innerHTML = `<img src="${agent.icon}" alt="${agent.name}" onerror="this.style.opacity='0.4'">`;
                btn.onclick = () => selectAgent(agent.name, btn);
                grid.appendChild(btn);
            });
        }

        function selectAgent(name, btn) {
            selectedAgent = name;
            document.querySelectorAll('.agent-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('lock-btn').innerText = `${name.toUpperCase()} ${t('btn_lock')}`;
            document.getElementById('lock-status').innerHTML = `<span style="color:var(--success); font-weight:800;">${name} ${t('ready_to_lock')}</span>`;
        }

        async function startLocking() {
            if (!selectedAgent) return showNotification(t('select_agent_prompt'), 'error');
            const statusEl = document.getElementById('lock-status');
            statusEl.innerHTML = `<div class="skin-spinner"></div><span class="loading-text">${selectedAgent.toUpperCase()} ${t('locking')}</span>`;
            try {
                await fetch(`/api/lock/${selectedAgent}`);
                showNotification(`${selectedAgent} ${t('at_lock_active')}`, 'success');
            } catch(e) { 
                showNotification(t('conn_error'), 'error'); 
                statusEl.innerText = "Error!";
            }
        }

        async function toggleAfk(checked) {
            isAfkActive = checked;
            await fetch(`/api/afk/${isAfkActive ? 'on' : 'off'}`);
            showNotification(isAfkActive ? t('afk_on') : t('afk_off'), isAfkActive ? 'success' : 'info');
        }

        // lastData declared at top

        function updateData() {
            fetch("/api/data")
                .then(r => r.json())
                .then(data => {
                    lastData = data;
                    updateDataFromObj(data);
                })
                .catch(err => {
                    console.warn("api/data fetch error:", err);
                });
        }

        function updateDataFromObj(data) {
                if (!data) return;
                const isConnected = Boolean(data.status && data.status.startsWith("Bağlı ("));
                $("#conn-ind").toggleClass("active", isConnected);
                $("#connection-status").text(isConnected ? t('system_active') : t('waiting_val'));
                
                let phaseText = "--:--";
                if (isConnected) {
                    const phaseKey = data.phase_key || "WAITING";
                    const phaseMap = LANG_DATA[currentLang].phases;
                    phaseText = phaseMap[phaseKey] || data.phase || phaseKey;
                }
                $("#match-timer").text(phaseText);

                if (data.map && data.map !== "Bilinmiyor") {
                    $("#current-map").text(data.map.toUpperCase());
                    $("#map-badge").css("display", "flex");
                } else {
                    $("#map-badge").css("display", "none");
                }
                const allPlayers = [...(data.allies || []), ...(data.enemies || [])];
                const pt = {};
                allPlayers.forEach(p => { if (p.party_id && p.party_id !== "00000000-0000-0000-0000-000000000000") pt[p.party_id] = (pt[p.party_id] || 0) + 1; });
                const pm = {}; let pIdx = 1;
                const COLORS = ['#ff4655', '#00f591', '#00d4ff', '#ffb700', '#c084fc', '#fb923c'];
                allPlayers.forEach(p => { 
                    if (p.is_premade && p.party_label) {
                        pm[p.party_id] = { i: p.party_label.replace('GRP ', ''), c: p.party_color || COLORS[(pIdx-1)%COLORS.length] };
                    } else if (p.party_id && pt[p.party_id] > 1 && !pm[p.party_id]) {
                        pm[p.party_id] = { i: pIdx++, c: COLORS[(pIdx-2)%COLORS.length] }; 
                    }
                });

                if (data.allies) {
                    const me = data.allies.find(p => p.is_me);
                    const btn = document.getElementById('lock-btn');
                    if (me && me.locked && me.agent !== "Seçiyor...") {
                        btn.innerText = t('btn_locked');
                        btn.disabled = true;
                        btn.style.opacity = "0.5";
                        document.getElementById('lock-status').innerHTML = `
                            <span style="color:var(--success); font-weight:900;">${me.agent.toUpperCase()} ${t('btn_locked')}!</span>
                            <div class="lock-refresh-note">${t('lock_refresh_note')}</div>
                        `;
                    }
                }
                renderPlayers("#ally-container", data.allies, pm, "#ally-summary", "ally");
                renderPlayers("#enemy-container", data.enemies, pm, "#enemy-summary", "enemy");
        }

        function renderPlayers(containerSelector, players, pm, summarySelector, teamType) {
            const container = $(containerSelector);
            container.empty();
            if (!players || players.length === 0) {
                const isEnemy = teamType === 'enemy';
                const accentColor = isEnemy ? 'var(--accent)' : 'var(--success)';
                container.append(`
                    <div class="empty-state-wrapper">
                        <div class="radar-pulse" style="background-color:${accentColor}; box-shadow: 0 0 15px ${accentColor}"></div>
                        <div class="empty-title">${t('scanning')}</div>
                        <div class="empty-subtitle">${t('waiting_data')}</div>
                    </div>
                `);
                if (summarySelector) $(summarySelector).text("");
                return;
            }
            if (summarySelector) {
                if (teamType === 'enemy') {
                    $(summarySelector).text("");
                } else {
                    let s = 0, g = new Set();
                    (players || []).forEach(p => { 
                        if (p.is_premade && p.party_label && p.party_label !== "SOLO") {
                            g.add(p.party_label);
                        } else if (p.party_id && pm[p.party_id]) {
                            g.add(pm[p.party_id].i);
                        } else {
                            s++;
                        }
                    });
                    const groupCount = g.size;
                    const summaryText = currentLang === 'tr' ? `${groupCount} GRUP | ${s} TEK` : `${groupCount} GROUPS | ${s} SOLO`;
                    $(summarySelector).text(summaryText);
                }
            }
            players.forEach(p => {
                const kpStyle = p.rank === "Radyant" || p.rank.includes("İmmo") ? "color:#ffb100" : "color:rgba(255,255,255,0.4)";
                const kpDisplay = (p.kp !== undefined && p.rank !== "Unranked") ? `<div class="rank-kp-v10" style="${kpStyle}">${p.kp} KP</div>` : '';
                
                let peakDisplay = '';
                const pPeak = (p.peak_rank_obj && p.peak_rank_obj[currentLang]) ? p.peak_rank_obj[currentLang] : (p.peak_rank || "");
                if (pPeak && pPeak !== "Unranked" && pPeak !== "Bilinmiyor" && pPeak !== "Unknown") {
                    const peakIconHtml = p.peak_rank_image ? `<img src="${p.peak_rank_image}" style="width:11px; height:11px; object-fit:contain; filter:drop-shadow(0 0 2px rgba(0,0,0,0.8)); flex-shrink:0;">` : '';
                    peakDisplay = `<div class="rank-peak-v10" title="Kariyer Zirve: ${pPeak}">${peakIconHtml}<span>${pPeak}</span></div>`;
                }
                
                let partyTag = '';
                if (teamType !== 'enemy') {
                    if (p.is_premade && p.party_label && p.party_label !== "SOLO") {
                        const c = p.party_color || '#8b5cf6';
                        partyTag = `<span class="party-tag" style="color:${c}; border-color:${c}55; background:${c}18; box-shadow:0 0 8px ${c}22;"><span class="party-tag-dot" style="background:${c}; box-shadow:0 0 5px ${c};"></span><span class="party-tag-text">${p.party_label}</span></span>`;
                    } else if (p.party_id && pm[p.party_id]) {
                        const c = pm[p.party_id].c || '#8b5cf6';
                        partyTag = `<span class="party-tag" style="color:${c}; border-color:${c}55; background:${c}18; box-shadow:0 0 8px ${c}22;"><span class="party-tag-dot" style="background:${c}; box-shadow:0 0 5px ${c};"></span><span class="party-tag-text">GRP ${pm[p.party_id].i}</span></span>`;
                    }
                }
                
                let incognitoTag = '';
                
                const skins = ['vandal', 'phantom', 'ghost', 'op', 'sheriff'].map(w => {
                    const skinData = p[w+'_obj'] || {};
                    const name = skinData[currentLang] || p[w] || "-";
                    const img = p[w+'_img'];
                    if (name === "-" || !name) return `<div class="skin-item"><div class="skin-spinner" style="margin:10px"></div></div>`;
                    return `<div class="skin-item" title="${name}">
                        <div class="skin-icon-v6" style="background-image: url('${img}?v=10')"></div>
                        <div class="skin-name-v6">${name}</div>
                    </div>`;
                }).join('');

                // Final Silhouette Fix (v44.26)
                const mysteryAgent = 'https://media.valorant-api.com/agents/add6443a-4571-4c46-bd0a-ce87ee364b67/bustportrait.png';
                let agentSrc = mysteryAgent;
                let agentClass = "agent-icon-v9";
                const agentName = (p.agent_obj && p.agent_obj[currentLang]) ? p.agent_obj[currentLang] : p.agent;

                if (p.agent !== "SELECTING" && p.agent_uuid && p.agent_uuid.length > 20) {
                    const agentImg = p.agent_image || `https://media.valorant-api.com/agents/${p.agent_uuid}/displayicon.png`;
                    if (agentImg && !agentImg.includes("//displayicon.png")) {
                        agentSrc = agentImg;
                    } else {
                        agentSrc = mysteryAgent;
                    }
                } else {
                    agentSrc = mysteryAgent;
                }
                let pNameBase = (p.name_obj && p.name_obj[currentLang]) ? p.name_obj[currentLang] : (p.player_name || p.name || "");
                const isHiddenName = (p.is_incognito && !p.is_me) || p.is_hidden_name || !pNameBase || pNameBase === "#" || pNameBase === "None#None" || pNameBase.trim() === "" || pNameBase === "Bilinmiyor" || pNameBase === "Unknown" || pNameBase === "Gizli" || pNameBase === "Hidden" || pNameBase.endsWith("#???");
                
                let pDisplayName = "";
                let pTagDisplay = "";
                if (isHiddenName) {
                    pDisplayName = t('hidden_player');
                    pTagDisplay = "";
                } else {
                    const pNameParts = pNameBase.split('#');
                    pDisplayName = pNameParts[0];
                    pTagDisplay = pNameParts[1] ? '#' + pNameParts[1] : '';
                }
                const pNameDisplay = `<span class="player-name-v9 ${p.is_me ? 'is-me' : ''} ${isHiddenName ? 'is-hidden-name' : ''}">${pDisplayName}</span><span class="discriminator-v10">${pTagDisplay}</span>`;

                const isLvlHidden = !p.level || p.level === "0" || p.level === 0 || p.hide_level;
                const lvlBadgeText = isLvlHidden ? '-' : p.level;
                const lvlTooltip = isLvlHidden ? t('hidden_level') : ('Level ' + p.level);

                const row = `<div class="player-row ${teamType} ${p.is_me ? 'me' : ''}" onclick="openPlayerModal('${p.puuid}')" title="Detaylı tüm silah ve skin envanterini görmek için tıkla">
                    <div class="rank-card">
                        <img src="${p.rank_image}" class="rank-icon-v10">
                        <div class="rank-name-v10">${(p.rank_obj && p.rank_obj[currentLang]) ? p.rank_obj[currentLang] : (p.rank || "Unknown")}</div>
                        ${kpDisplay}
                        ${peakDisplay}
                    </div>
                    <div class="profile-card">
                        <div class="agent-box-v13 ${p.agent === "SELECTING" ? 'is-selecting' : ''}">
                            <img src="${agentSrc}" class="${agentClass}" onerror="this.src='https://media.valorant-api.com/agents/add6443a-4571-4c46-bd0a-ce87ee364b67/displayicon.png'; this.parentNode.classList.add('is-selecting');">
                            <div class="mystery-q">?</div>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px; margin-top:2px;">
                            <div class="agent-name-v10">${agentName}</div>
                            <div class="level-badge" title="${lvlTooltip}">${lvlBadgeText}</div>
                        </div>
                    </div>
                    <div class="info-block">
                        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                            <div style="display:flex; align-items:baseline;">
                                ${pNameDisplay}
                            </div>
                            ${partyTag}
                        </div>
                    </div>
                    <div class="skin-deck">${skins}</div>
                </div>`;
                container.append(row);
            });
        }

        // CURRENT_MODAL_PLAYER & CURRENT_MODAL_FILTER declared at top

        function openPlayerModal(puuid) {
            if (!lastData) return;
            const allPlayers = (lastData.allies || []).concat(lastData.enemies || []);
            const player = allPlayers.find(p => p.puuid === puuid);
            if (!player) return;

            CURRENT_MODAL_PLAYER = player;
            CURRENT_MODAL_FILTER = 'all';

            let pName = (player.name_obj && player.name_obj[currentLang]) ? player.name_obj[currentLang] : (player.player_name || player.name || "");
            const isHiddenPlayer = (player.is_incognito && !player.is_me) || player.is_hidden_name || !pName || pName === "#" || pName === "None#None" || pName.trim() === "" || pName === "Bilinmiyor" || pName === "Unknown" || pName === "Gizli" || pName === "Hidden" || pName.endsWith("#???");

            if (isHiddenPlayer) {
                $('#pm-player-name').text(t('hidden_player'));
                $('#pm-player-tag').text('');
            } else {
                const parts = pName.split('#');
                $('#pm-player-name').text(parts[0] || t('hidden_player'));
                $('#pm-player-tag').text(parts[1] ? '#' + parts[1] : '');
            }

            const agentImg = player.agent_image || `https://media.valorant-api.com/agents/${player.agent_uuid}/displayicon.png`;
            $('#pm-agent-img').attr('src', agentImg || 'https://media.valorant-api.com/agents/add6443a-4571-4c46-bd0a-ce87ee364b67/displayicon.png');
            
            if (player.rank_image) {
                $('#pm-rank-img').attr('src', player.rank_image).show();
            } else {
                $('#pm-rank-img').hide();
            }

            const rankName = (player.rank_obj && player.rank_obj[currentLang]) ? player.rank_obj[currentLang] : (player.rank || "Unranked");
            const kpText = (player.kp !== undefined && player.rank !== "Unranked") ? ` (${player.kp} KP)` : '';
            const rankImgHtml = player.rank_image ? `<img src="${player.rank_image}" class="badge-rank-icon" alt="">` : '';
            $('#pm-rank-badge').html(`${rankImgHtml}<span>${rankName}${kpText}</span>`);
            const isModalLvlHidden = !player.level || player.level === '0' || player.level === 0 || player.hide_level;
            const lvlModalText = isModalLvlHidden ? `LVL ${t('hidden_level')}` : `LVL ${player.level}`;
            $('#pm-level-badge').text(lvlModalText);

            const peakName = (player.peak_rank_obj && player.peak_rank_obj[currentLang]) ? player.peak_rank_obj[currentLang] : (player.peak_rank || "");
            if (peakName && peakName !== "Unranked" && peakName !== "Bilinmiyor" && peakName !== "Unknown") {
                const peakLabel = t('peak_rank') || 'PEAK';
                const peakImgHtml = player.peak_rank_image ? `<img src="${player.peak_rank_image}" class="badge-rank-icon" alt="">` : '';
                $('#pm-peak-badge').html(`${peakImgHtml}<span>${peakLabel}: ${peakName}</span>`).show();
            } else {
                $('#pm-peak-badge').hide();
            }

            const isPremade = (player.is_premade && player.party_label && player.party_label !== 'SOLO') || (player.party_id && pt[player.party_id] > 1);
            const partyLabel = player.party_label || (player.party_id && pm[player.party_id] ? `GRP ${pm[player.party_id].i}` : '');
            const partyText = isPremade ? `${t('party_group')} (${partyLabel || 'PREMADE'})` : t('party_solo');
            $('#pm-party-badge').text(partyText);
            if (isPremade && player.party_color) {
                $('#pm-party-badge').css({'color': player.party_color, 'border-color': player.party_color, 'background': player.party_color + '18'});
            } else {
                $('#pm-party-badge').css({'color': '', 'border-color': '', 'background': ''});
            }

            $('#pm-incognito-badge').remove();

            const premCount = player.premium_count || (player.all_weapons || []).filter(w => w.is_premium).length;
            $('#pm-prem-badge').text(`★ ${premCount} ${t('special_skins')}`);

            renderModalWeaponCards(player.all_weapons || []);

            // Arka plan sayfasının kaymasını engelle
            document.body.style.overflow = 'hidden';

            const modal = $('#player-skins-modal');
            modal.css('display', 'flex');
            setTimeout(() => modal.addClass('is-active'), 10);
        }

        function closePlayerModal() {
            const modal = $('#player-skins-modal');
            modal.removeClass('is-active');
            setTimeout(() => modal.css('display', 'none'), 300);
            // Arka plan sayfasının kaymasını tekrar serbest bırak
            document.body.style.overflow = '';
            CURRENT_MODAL_PLAYER = null;
        }

        function renderModalWeaponCards(weapons) {
            const grid = $('#pm-weapons-grid');
            grid.empty();

            if (!weapons || weapons.length === 0) {
                grid.html('<div style="grid-column:1/-1; text-align:center; padding:40px; color:#888; font-size:1.1em;">Envanter verisi henüz yüklenmedi veya lobi bekleniyor...</div>');
                return;
            }

            weapons.forEach(w => {
                const sName = currentLang === 'en' ? (w.skin_name_en || w.skin_name) : (w.skin_name || w.skin_name_en);
                const isKnife = w.category === 'melee';
                const isPrem = w.is_premium;

                let cardClass = 'weapon-card';
                if (isKnife) cardClass += ' is-knife';
                else if (isPrem) cardClass += ' is-premium';

                let badgeHtml = `<span class="w-status-badge badge-std">${t('badge_standard')}</span>`;
                if (isKnife) badgeHtml = `<span class="w-status-badge badge-knife">${t('badge_knife')}</span>`;
                else if (isPrem) badgeHtml = `<span class="w-status-badge badge-prem">${t('badge_premium')}</span>`;

                const catName = currentLang === 'en' ? (w.category_name_en || w.category_name) : (w.category_name || w.category_name_en);
                const wName = currentLang === 'en' ? (w.name_en || w.name) : (w.name || w.name_en);

                const cardHtml = `
                    <div class="${cardClass}">
                        <div class="weapon-card-top">
                            <span class="w-name-badge">${wName}</span>
                            ${badgeHtml}
                        </div>
                        <div class="weapon-card-img-wrap">
                            <img src="${w.icon || 'https://media.valorant-api.com/weapons/2f59173c-4bed-4c60-ba37-647314299aa2/displayicon.png'}" 
                                 alt="${sName}" 
                                 onerror="this.src='https://media.valorant-api.com/weapons/2f59173c-4bed-4c60-ba37-647314299aa2/displayicon.png'">
                        </div>
                        <div class="weapon-card-bottom">
                            <div class="skin-title" title="${sName}">${sName}</div>
                            <div class="skin-category-sub">${catName}</div>
                        </div>
                    </div>
                `;
                grid.append(cardHtml);
            });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closePlayerModal();
                toggleModal(false);
                toggleAfkModal(false);
            }
        });

        let appInitialized = false;
        function initApp() {
            if (appInitialized) return;
            appInitialized = true;
            initVFX();
            setLanguage(currentLang);
            fetchAgents();
            setInterval(updateData, 2000);
            updateData();
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initApp);
        } else {
            initApp();
        }
        if (typeof $ !== 'undefined') {
            $(document).ready(initApp);
        }
    </script>
</body>
</html>
"""

DEFAULT_PLAYABLE_AGENTS = {
    "Jett": ("add6443a-41bd-e414-f6ad-e58d267f4e95", "Düellocu", "https://media.valorant-api.com/agents/add6443a-41bd-e414-f6ad-e58d267f4e95/displayicon.png"),
    "Reyna": ("a3bfb853-43b2-7238-a4f1-ad90e9e46bcc", "Düellocu", "https://media.valorant-api.com/agents/a3bfb853-43b2-7238-a4f1-ad90e9e46bcc/displayicon.png"),
    "Raze": ("f94c3b30-42be-e959-889c-5aa313dba261", "Düellocu", "https://media.valorant-api.com/agents/f94c3b30-42be-e959-889c-5aa313dba261/displayicon.png"),
    "Phoenix": ("eb93336a-449b-9c1b-0a54-a891f7921d69", "Düellocu", "https://media.valorant-api.com/agents/eb93336a-449b-9c1b-0a54-a891f7921d69/displayicon.png"),
    "Yoru": ("7f94d92c-4234-0a36-9646-3a87eb8b5c89", "Düellocu", "https://media.valorant-api.com/agents/7f94d92c-4234-0a36-9646-3a87eb8b5c89/displayicon.png"),
    "Neon": ("bb2a4828-46eb-8cd1-e765-15848195d751", "Düellocu", "https://media.valorant-api.com/agents/bb2a4828-46eb-8cd1-e765-15848195d751/displayicon.png"),
    "Iso": ("0e38b510-41a8-5780-5e8f-568b2a4f2d6c", "Düellocu", "https://media.valorant-api.com/agents/0e38b510-41a8-5780-5e8f-568b2a4f2d6c/displayicon.png"),
    "Waylay": ("df1cb487-4902-002e-5c17-d28e83e78588", "Düellocu", "https://media.valorant-api.com/agents/df1cb487-4902-002e-5c17-d28e83e78588/displayicon.png"),
    "Omen": ("8e253930-4c05-31dd-1b6c-968525494517", "Kontrol Uzmanı", "https://media.valorant-api.com/agents/8e253930-4c05-31dd-1b6c-968525494517/displayicon.png"),
    "Clove": ("1dbf2edd-4729-0984-3115-daa5eed44993", "Kontrol Uzmanı", "https://media.valorant-api.com/agents/1dbf2edd-4729-0984-3115-daa5eed44993/displayicon.png"),
    "Brimstone": ("9f0d8ba9-4140-b941-57d3-a7ad57c6b417", "Kontrol Uzmanı", "https://media.valorant-api.com/agents/9f0d8ba9-4140-b941-57d3-a7ad57c6b417/displayicon.png"),
    "Viper": ("707eab51-4836-f488-046a-cda6bf494859", "Kontrol Uzmanı", "https://media.valorant-api.com/agents/707eab51-4836-f488-046a-cda6bf494859/displayicon.png"),
    "Astra": ("41fb69c1-4189-7b37-f117-bcaf1e96f1bf", "Kontrol Uzmanı", "https://media.valorant-api.com/agents/41fb69c1-4189-7b37-f117-bcaf1e96f1bf/displayicon.png"),
    "Harbor": ("95b78ed7-4637-86d9-7e41-71ba8c293152", "Kontrol Uzmanı", "https://media.valorant-api.com/agents/95b78ed7-4637-86d9-7e41-71ba8c293152/displayicon.png"),
    "Miks": ("7c8a4701-4de6-9355-b254-e09bc2a34b72", "Kontrol Uzmanı", "https://media.valorant-api.com/agents/7c8a4701-4de6-9355-b254-e09bc2a34b72/displayicon.png"),
    "Sova": ("320b2a48-4d9b-a075-30f1-1f93a9b638fa", "Öncü", "https://media.valorant-api.com/agents/320b2a48-4d9b-a075-30f1-1f93a9b638fa/displayicon.png"),
    "Fade": ("dade69b4-4f5a-8528-247b-219e5a1facd6", "Öncü", "https://media.valorant-api.com/agents/dade69b4-4f5a-8528-247b-219e5a1facd6/displayicon.png"),
    "Breach": ("5f8d3a7f-467b-97f3-062c-13acf203c006", "Öncü", "https://media.valorant-api.com/agents/5f8d3a7f-467b-97f3-062c-13acf203c006/displayicon.png"),
    "Skye": ("6f2a04ca-43e0-be17-7f36-b3908627744d", "Öncü", "https://media.valorant-api.com/agents/6f2a04ca-43e0-be17-7f36-b3908627744d/displayicon.png"),
    "KAY/O": ("601dbbe7-43ce-be57-2a40-4abd24953621", "Öncü", "https://media.valorant-api.com/agents/601dbbe7-43ce-be57-2a40-4abd24953621/displayicon.png"),
    "Gekko": ("e370fa57-4757-3604-3648-499e1f642d3f", "Öncü", "https://media.valorant-api.com/agents/e370fa57-4757-3604-3648-499e1f642d3f/displayicon.png"),
    "Tejo": ("b444168c-4e35-8076-db47-ef9bf368f384", "Öncü", "https://media.valorant-api.com/agents/b444168c-4e35-8076-db47-ef9bf368f384/displayicon.png"),
    "Killjoy": ("1e58de9c-4950-5125-93e9-a0aee9f98746", "Gözcü", "https://media.valorant-api.com/agents/1e58de9c-4950-5125-93e9-a0aee9f98746/displayicon.png"),
    "Cypher": ("117ed9e3-49f3-6512-3ccf-0cada7e3823b", "Gözcü", "https://media.valorant-api.com/agents/117ed9e3-49f3-6512-3ccf-0cada7e3823b/displayicon.png"),
    "Sage": ("569fdd95-4d10-43ab-ca70-79becc718b46", "Gözcü", "https://media.valorant-api.com/agents/569fdd95-4d10-43ab-ca70-79becc718b46/displayicon.png"),
    "Chamber": ("22697a3d-45bf-8dd7-4fec-84a9e28c69d7", "Gözcü", "https://media.valorant-api.com/agents/22697a3d-45bf-8dd7-4fec-84a9e28c69d7/displayicon.png"),
    "Deadlock": ("cc8b64c8-4b25-4ff9-6e7f-37b4da43d235", "Gözcü", "https://media.valorant-api.com/agents/cc8b64c8-4b25-4ff9-6e7f-37b4da43d235/displayicon.png"),
    "Vyse": ("efba5359-4016-a1e5-7626-b1ae76895940", "Gözcü", "https://media.valorant-api.com/agents/efba5359-4016-a1e5-7626-b1ae76895940/displayicon.png"),
    "Veto": ("92eeef5d-43b5-1d4a-8d03-b3927a09034b", "Gözcü", "https://media.valorant-api.com/agents/92eeef5d-43b5-1d4a-8d03-b3927a09034b/displayicon.png")
}
AGENTS = {name: data[0] for name, data in DEFAULT_PLAYABLE_AGENTS.items()}
AGENT_DATA = {name: {"uuid": data[0], "role": data[1], "icon": data[2]} for name, data in DEFAULT_PLAYABLE_AGENTS.items()}

def fetch_agent_database():
    """Valorant-api.com'dan en güncel ajan listesini ve rollerini çeker"""
    global AGENTS, AGENT_DATA
    try:
        response = requests.get("https://valorant-api.com/v1/agents", params={"language": "tr-TR", "isPlayableCharacter": "true"}, timeout=8)
        if response.status_code == 200:
            data_api = response.json().get("data", [])
            if len(data_api) > 0:
                AGENTS.clear()
                AGENT_DATA.clear()
                for agent in data_api:
                    name = agent.get("displayName")
                    uuid = agent.get("uuid")
                    role = agent.get("role", {}).get("displayName", "Diğer")
                    icon = heal_url(agent.get("displayIcon"))
                    
                    if name and uuid:
                        clean_name = name.title() if name != "KAY/O" else "KAY/O"
                        AGENTS[clean_name] = uuid
                        AGENT_DATA[clean_name] = {
                            "uuid": uuid,
                            "role": role,
                            "icon": icon
                        }
                return True
    except:
        pass
    return len(AGENT_DATA) > 0

VAL_MAPS = {
    "/Game/Maps/Ascent/Ascent": "Ascent",
    "/Game/Maps/Bonsai/Bonsai": "Split",
    "/Game/Maps/Duality/Duality": "Bind",
    "/Game/Maps/Foxtrot/Foxtrot": "Breeze",
    "/Game/Maps/Canyon/Canyon": "Fracture",
    "/Game/Maps/Triad/Triad": "Haven",
    "/Game/Maps/Port/Port": "Icebox",
    "/Game/Maps/Jam/Jam": "Lotus",
    "/Game/Maps/Pitt/Pitt": "Pearl",
    "/Game/Maps/Duality/Split": "Split",
    "/Game/Maps/Jungle/Sunset": "Sunset",
    "/Game/Maps/Jungle/Jungle": "Sunset",
    "/Game/Maps/Jungle/Juliet": "Sunset",
    "/Game/Maps/Juliet/Juliet": "Sunset", # v27.3: Adding deeper Juliet folder ID
    "/Game/Maps/Juliet/Sunset": "Sunset", # v27.3: Adding hybrid ID
    "Juliet": "Sunset",
    "Juliett": "Sunset", # v27.4: Fixing double T spelling
    "Jungle": "Sunset",
    "/Game/Maps/Juliett/Juliett": "Sunset", # v27.4: Double T path
    "/Game/Maps/Rook/Rook": "Corrode",
    "/Game/Maps/Infinity/Infinity": "Abyss", # v25.7: User debug confirmed Abyss
    "/Game/Maps/Extraction/Abyss": "Abyss",
    "/Game/Maps/Corrode/Corrode": "Abyss", # Keeping as fallback
    "/Game/Maps/Plummet/Plummet": "Summit", # Riot codename Plummet -> Summit
    "/Game/Maps/Plummet/Summit": "Summit",
    "Plummet": "Summit",
    "Summit": "Summit",
    "/Game/Maps/HURM/HURM_P/HURM_P": "District (TDM)",
    "/Game/Maps/HURM/HURM_Q/HURM_Q": "Piazza (TDM)",
    "/Game/Maps/HURM/HURM_R/HURM_R": "Kasbah (TDM)",
    "/Game/Maps/HURM/HURM_S/HURM_S": "Drift (TDM)",
    "/Game/Maps/HURM/HURM_T/HURM_T": "Corrode (TDM)",
}

RANK_NAMES = {
    0: "Unranked", 1: "Unranked", 2: "Unranked",
    3: "Demir 1", 4: "Demir 2", 5: "Demir 3",
    6: "Bronz 1", 7: "Bronz 2", 8: "Bronz 3",
    9: "Gümüş 1", 10: "Gümüş 2", 11: "Gümüş 3",
    12: "Altın 1", 13: "Altın 2", 14: "Altın 3",
    15: "Platin 1", 16: "Platin 2", 17: "Platin 3",
    18: "Elmas 1", 19: "Elmas 2", 20: "Elmas 3",
    21: "Yüce 1", 22: "Yüce 2", 23: "Yüce 3",
    24: "İmmo 1", 25: "İmmo 2", 26: "İmmo 3",
    27: "Radyant"
}

RANK_NAMES_EN = {
    0: "Unranked", 1: "Unranked", 2: "Unranked",
    3: "Iron 1", 4: "Iron 2", 5: "Iron 3",
    6: "Bronze 1", 7: "Bronze 2", 8: "Bronze 3",
    9: "Silver 1", 10: "Silver 2", 11: "Silver 3",
    12: "Gold 1", 13: "Gold 2", 14: "Gold 3",
    15: "Platinum 1", 16: "Platinum 2", 17: "Platinum 3",
    18: "Diamond 1", 19: "Diamond 2", 20: "Diamond 3",
    21: "Ascendant 1", 22: "Ascendant 2", 23: "Ascendant 3",
    24: "Immortal 1", 25: "Immortal 2", 26: "Immortal 3",
    27: "Radiant"
}

# Skin Veritabanı (Başlangıçta boş)
SKIN_CACHE = {}

# fetch_skin_database removed (Duplicate of line 52)

# Anti-AFK WinAPI Yapıları
PUL = ctypes.POINTER(ctypes.c_ulong)
class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]
class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]
class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]
class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]
class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

# Tuş Kodları (Scan Codes)
KEYS = {
    'W': 0x11,
    'A': 0x1E,
    'S': 0x1F,
    'D': 0x20,
    'SPACE': 0x39
}

# Sanal Tuş Kodları (Virtual Keys - Arka plan için)
VK_KEYS = {
    'W': 0x57,
    'A': 0x41,
    'S': 0x53,
    'D': 0x44,
    'SPACE': 0x20
}

def send_key_background(hwnd, vk_code, scan_code):
    """Belirli bir pencereye (arka planda olsa bile) gerçekçi tuş komutu gönderir"""
    if not hwnd: return
    
    # Unreal Engine'in (Valorant) algılaması için scan code içeren lParam yapıları
    # WM_KEYDOWN = 0x0100, WM_KEYUP = 0x0101
    lParam_down = (scan_code << 16) | 0x00000001
    lParam_up = (scan_code << 16) | 0xC0000001
    
    ctypes.windll.user32.PostMessageW(hwnd, 0x0100, vk_code, lParam_down)
    time.sleep(random.uniform(0.05, 0.1)) # Tuşa basılı tutma simülasyonu
    ctypes.windll.user32.PostMessageW(hwnd, 0x0101, vk_code, lParam_up)

def press_key(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def release_key(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008 | 0x0002, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))


def get_lockfile():
    local_app_data = os.getenv('LOCALAPPDATA')
    if not local_app_data:
        return None
    path = os.path.join(local_app_data, 'Riot Games', 'Riot Client', 'Config', 'lockfile')
    try:
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            data = f.read().strip().split(':')
            if len(data) >= 4:
                return {'port': data[2], 'password': data[3]}
    except Exception:
        pass
    return None


class Locker:
    def __init__(self, lockfile):
        self.port = lockfile['port']
        self.password = lockfile['password']
        self.lockfile = lockfile # Ekledik
        self.base_url = f"https://127.0.0.1:{self.port}"
        self.auth = base64.b64encode(f"riot:{self.password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {self.auth}"}
        self.session = requests.Session()
        self.session.verify = False
        adapter = requests.adapters.HTTPAdapter(pool_connections=25, pool_maxsize=25, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self.puuid = None
        self.access_token = None
        self.entitlements = None
        self.version = None
        self.shard = "eu" # Varsayılan EU (TR)
        self.region = "eu"
        self._name_cache = {} # Sadece RAM / Hafıza isim önbelleği (Diske yazılmaz, tertemiz)
        self._rank_cache = {} # Kalıcı rütbe önbelleği
        self._tier_cache = {} # Kalıcı tier id önbelleği
        self._kp_cache = {}   # v38.0: Kalıcı KP önbelleği
        self._level_cache = {} # Kalıcı seviye önbelleği
        self._peak_tier_cache = {} # Kariyer zirve rütbe önbelleği
        self._bg_resolving = set()

    def cache_name(self, puuid, name):
        if not puuid or not name:
            return
        invalid = {"Bilinmiyor", "#", "?#?", "None#None", "Unknown", "", "Gizli"}
        if name in invalid or name.endswith("#???") or "(Gizli)" in name:
            return
        # Sadece RAM'de tut
        self._name_cache[puuid] = name

    def start_background_name_resolver(self, missing_puuids, match_id=None):
        """Gizli moddaki oyuncuların tercihlerine saygı duyulur, arka planda isim çözme zorlaması yapılmaz"""
        pass

    def connect(self):
        try:
            # 1. Valorant-Client RSO Access Token & PUUID al (Riot son güncellemelerde riot-client tokenlarına BAD_CLAIMS veriyor)
            r_rso = self.session.get(f"{self.base_url}/rso-auth/v2/authorizations/valorant-client", headers=self.headers)
            if r_rso.status_code == 200:
                auth_data = r_rso.json().get("authorization", {})
                self.access_token = auth_data.get("accessToken", {}).get("token")
                
                # Token'dan veya entitlements'tan PUUID çıkar
                try:
                    payload = self.access_token.split(".")[1]
                    payload += "=" * ((4 - len(payload) % 4) % 4)
                    claims = json.loads(base64.urlsafe_b64decode(payload.encode()))
                    self.puuid = claims.get("sub")
                except:
                    pass
            
            # Fallback PUUID ve token eğer rso alınamazsa
            if not self.puuid or not self.access_token:
                r = self.session.get(f"{self.base_url}/entitlements/v1/token", headers=self.headers)
                if r.status_code == 200:
                    data = r.json()
                    self.puuid = self.puuid or data.get('subject')
                    self.access_token = self.access_token or data.get('accessToken')
                    self.entitlements = data.get('token')

            # 2. Entitlements Token al (valorant-client access token ile Riot Entitlements API üzerinden)
            if self.access_token:
                try:
                    r_ent = requests.post(
                        "https://entitlements.auth.riotgames.com/api/token/v1",
                        headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"},
                        json={},
                        timeout=5
                    )
                    if r_ent.status_code == 200:
                        self.entitlements = r_ent.json().get("entitlements_token")
                except:
                    pass

            # Eğer external entitlements alınamadıysa local fallback
            if not self.entitlements:
                r_local = self.session.get(f"{self.base_url}/entitlements/v1/token", headers=self.headers)
                if r_local.status_code == 200:
                    self.entitlements = r_local.json().get('token')

            if self.access_token and self.entitlements:
                r2 = self.session.get(f"{self.base_url}/product-session/v1/external-sessions", headers=self.headers)
                if r2.status_code == 200:
                    for sid, sdata in r2.json().items():
                        if sdata.get("productId") == "valorant":
                            # Shard ve Region tespiti
                            launch_args = sdata.get("launchConfiguration", {}).get("arguments", [])
                            for arg in launch_args:
                                if arg.startswith("-pp="):
                                    self.region = arg.split("=")[1]
                                if arg.startswith("-shard="):
                                    self.shard = arg.split("=")[1]
                            self.version = sdata.get("version")
                            break

                # ShooterGame.log dosyasından versiyonu çek (En Garantisi)
                if not self.version or "-shipping-" not in self.version:
                    try:
                        local_appdata = os.getenv('LOCALAPPDATA')
                        log_path = os.path.join(local_appdata, "VALORANT", "Saved", "Logs", "ShooterGame.log")
                        if os.path.exists(log_path):
                            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                                for line in f:
                                    if "CI server version:" in line:
                                        parts = line.split("CI server version:")
                                        if len(parts) > 1:
                                            self.version = parts[1].strip()
                                            if "-shipping-" not in self.version and len(self.version.split("-")) == 4:
                                                v_parts = self.version.split("-")
                                                self.version = f"{v_parts[0]}-{v_parts[1]}-shipping-{v_parts[2]}-{v_parts[3]}"
                                            break
                    except:
                        pass

                # Son çare valorant-api.com üzerinden en güncel Client Version çek
                if not self.version:
                    try:
                        r_ver = requests.get("https://valorant-api.com/v1/version", timeout=4).json()
                        self.version = r_ver.get("data", {}).get("riotClientVersion")
                    except:
                        pass

                return True
        except:
            pass
        return False
    
    def get_headers(self):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Riot-Entitlements-JWT": self.entitlements,
            "Content-Type": "application/json",
            "User-Agent": "RiotClient/43.0.1.4393933.4384232 rso-auth (Windows;10;;Professional, x64)",
            "X-Riot-ClientPlatform": "ewogICAgInBsYXRmb3JtVHlwZSI6ICJQQyIsCiAgICAicGxhdGZvcm1PUyI6ICJXaW5kb3dzIiwKICAgICJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjI2MjAwLjEuMjU2LjY0Yml0IiwKICAgICJwbGF0Zm9ybUNoaXBzZXQiOiAiVW5rbm93biIKfQ=="
        }
        if self.version:
            headers["X-Riot-ClientVersion"] = self.version
        return headers
    
    def get_match_loadouts(self, match_id):
        """Maçtaki oyuncuların loadout (skin) bilgilerini çeker"""
        try:
            # Local API yerine Remote (GLZ) API kullanalım
            url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/core-game/v1/matches/{match_id}/loadouts"
            response = self.session.get(url, headers=self.get_headers(), verify=False)
            
            if response.status_code == 200:
                data = response.json()
                return data["Loadouts"]
            else:
                console.print(f"[bold red]API Hatası ({response.status_code}): {response.text}[/bold red]")
        except Exception as e:
            console.print(f"[bold red]API Code Error: {e}[/bold red]")
            pass
        return []

    def get_pregame(self):
        """Pregame (karakter seçimi) kontrolü"""
        try:
            url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/pregame/v1/players/{self.puuid}"
            r = self.session.get(url, headers=self.get_headers(), verify=False)
            if r.status_code == 200:
                return r.json().get("MatchID")
        except:
            pass
        return None
    
    def get_coregame(self):
        """Core game (oyun içi) kontrolü"""
        try:
            url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/core-game/v1/players/{self.puuid}"
            r = self.session.get(url, headers=self.get_headers(), verify=False)
            if r.status_code == 200:
                return r.json().get("MatchID")
        except:
            pass
        return None
    
    def get_current_match(self):
        """Herhangi bir maçta mıyız kontrol et (pregame veya coregame)"""
        # Önce pregame kontrol
        match_id = self.get_pregame()
        if match_id:
            return match_id, "pregame"
        
        # Sonra coregame kontrol
        match_id = self.get_coregame()
        if match_id:
            return match_id, "coregame"
        
        return None, None
    
    def select_agent(self, match_id, agent_uuid):
        try:
            url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/pregame/v1/matches/{match_id}/select/{agent_uuid}"
            r = self.session.post(url, headers=self.get_headers(), json={}, verify=False)
            return r.status_code == 200
        except:
            return False
    
    def lock_agent(self, match_id, agent_uuid):
        try:
            url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/pregame/v1/matches/{match_id}/lock/{agent_uuid}"
            r = self.session.post(url, headers=self.get_headers(), json={}, verify=False)
            return r.status_code == 200
        except:
            return False
    
    def get_match_details(self, match_id):
        """Maç detaylarını al"""
        try:
            url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/pregame/v1/matches/{match_id}"
            r = self.session.get(url, headers=self.get_headers(), verify=False)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None
    
    def get_player_names(self, puuids):
        """Toplu şekilde oyuncu isimlerini al - Çok daha hızlı ve güvenilirdir"""
        results = {}
        to_fetch = []
        
        invalid_names = {"Bilinmiyor", "#", "?#?", "None#None", "Unknown", "", "Gizli"}
        
        for puuid in puuids:
            if not puuid:
                continue
            cached = self._name_cache.get(puuid)
            if cached and cached not in invalid_names:
                results[puuid] = cached
            else:
                to_fetch.append(puuid)
        
        if not to_fetch:
            return results

        # 1. Aşama: Yerel Chat Participants & Presences (/chat/v5/participants)
        try:
            r_cp = self.session.get(f"{self.base_url}/chat/v5/participants", headers=self.headers, verify=False, timeout=1.5)
            if r_cp.status_code == 200:
                for cp in r_cp.json().get("participants", []):
                    c_puuid = cp.get("puuid")
                    c_name = cp.get("game_name")
                    c_tag = cp.get("game_tag")
                    if c_puuid and c_name and c_tag and f"{c_name}#{c_tag}" not in invalid_names:
                        full_name = f"{c_name}#{c_tag}"
                        self.cache_name(c_puuid, full_name)
                        if c_puuid in to_fetch:
                            results[c_puuid] = full_name
        except Exception:
            pass

        # 2. Aşama: Remote PVP Name Service (PUT /name-service/v2/players)
        rem_fetch = [p for p in to_fetch if p not in results]
        if rem_fetch:
            try:
                url = f"https://pd.{self.shard}.a.pvp.net/name-service/v2/players"
                r = self.session.put(url, headers=self.get_headers(), json=rem_fetch, verify=False, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    for player in data:
                        puuid = player.get('Subject')
                        g_name = player.get('GameName')
                        t_line = player.get('TagLine')
                        d_name = player.get('DisplayName')
                        
                        full_name = None
                        # Sadece GERÇEK ve ETİKETLİ Riot ID geçerlidir!
                        if g_name and t_line and str(t_line).strip():
                            full_name = f"{g_name}#{t_line}"
                        elif d_name and "#" in d_name and not d_name.startswith("#") and not d_name.endswith("#"):
                            full_name = d_name
                        
                        # Eğer oyuncu gizli moddaysa ve Riot etiketi boş döndüyse (#???),
                        # ASLA bunu çözülmüş isim sayma, missing listesinde kalsın ki çözülsün!
                        if full_name and full_name not in invalid_names and not full_name.endswith("#???") and puuid:
                            self.cache_name(puuid, full_name)
                            results[puuid] = full_name
            except Exception:
                pass

        # Eksik kalan veya gizli isimler için "Gizli" ata
        for puuid in to_fetch:
            if puuid not in results:
                results[puuid] = "Gizli"
        
        return results

    def get_player_name(self, puuid):
        """Tekil oyuncu ismi al (Uyumluluk için)"""
        res = self.get_player_names([puuid])
        return res.get(puuid, "Bilinmiyor")
    def get_coregame_details(self, match_id):
        """Core game maç detaylarını al"""
        try:
            url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/core-game/v1/matches/{match_id}"
            r = self.session.get(url, headers=self.get_headers(), verify=False)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None

    def get_pregame_loadouts(self, match_id):
        """Pre-game skin bilgilerini al"""
        try:
            url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/pregame/v1/matches/{match_id}/loadouts"
            r = self.session.get(url, headers=self.get_headers(), verify=False)
            if r.status_code == 200:
                data = r.json()
                result = {}
                for l in data.get("Loadouts", []):
                    key = l.get("Subject", l.get("CharacterID"))
                    if key: result[key] = l.get("Loadout")
                return result
        except: pass
        return {}

    def get_coregame_loadouts(self, match_id):
        """Core game loadout (skin) bilgilerini al"""
        try:
            url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/core-game/v1/matches/{match_id}/loadouts"
            r = self.session.get(url, headers=self.get_headers(), verify=False)
            if r.status_code == 200:
                data = r.json()
                # Loadoutları oyuncu bazlı mapleyelim
                loadouts = {}
                for item in data.get("Loadouts", []):
                   loadouts[item.get("CharacterID")] = item.get("Loadout", {})
                   # Not: CharacterID aslında yanlış olabilir, Subject (puuid) olmayabilir.
                   # API'den dönen yapı: Loadouts -> [{CharacterID: "...", Loadout: {...}}, ...]
                   # Çoğu zaman bu CharacterID ajanı belirtir, oyuncuyu değil!
                   # AMA CoreGame Loadouts endpointi genellikle bu formatta döner.
                   # Düzeltme: CoreGame Loadouts endpointi direk PUUID vermez mi?
                   # API Dökümanına göre bu endpoint bazen sorunlu.
                   # Alternatif: Match detaylarından çekmek.
                   pass
                
                # İkinci deneme: Düzgün parse edelim
                # Bu endpoint: https://glz.../core-game/v1/matches/{matchID}/loadouts
                # Cevap: { "Loadouts": [ { "CharacterID": "...", "Loadout": ... } ] } 
                # Sorun: Burada CharacterID aslında Subject (Player PUUID) mi? Evet genellikle.
                
                result = {}
                for l in data.get("Loadouts", []):
                    # ÖNCELİKLE Subject (PUUID) kullanmalıyız!
                    # CharacterID genellikle Ajan ID'sidir ve benzersiz değildir (Mirror match varsa)
                    key = l.get("Subject", l.get("CharacterID"))
                    if key:
                        result[key] = l.get("Loadout")
                
                return result
        except:
            pass
        return {}

    def get_player_rank(self, puuid):
        """Oyuncunun rütbe (MMR), KP ve Kariyer Zirve (Peak) bilgisini al"""
        try:
            url = f"https://pd.{self.shard}.a.pvp.net/mmr/v1/players/{puuid}"
            headers = self.get_headers()
            r = self.session.get(url, headers=headers, verify=False, timeout=3)
            
            if r.status_code == 200:
                data = r.json()
                tier = 0
                kp = 0
                
                # 1. Yol: Competitive Updates (En hızlı ve genelde en güncel yol)
                last_update = data.get("LatestCompetitiveUpdate")
                if last_update and isinstance(last_update, dict):
                    tier = last_update.get("TierAfterUpdate", 0)
                    kp = last_update.get("RankedRatingAfterUpdate", 0)
                
                # 2. Yol: QueueSkills -> competitive
                if tier == 0:
                    try:
                        comp = data.get("QueueSkills", {}).get("competitive", {})
                        tier = comp.get("Tier", 0)
                        kp = comp.get("RankedRating", 0)
                    except: pass
                
                # 3. Yol: Seasonal Info
                seasonal = data.get("QueueSkills", {}).get("competitive", {}).get("SeasonalInfoBySeasonID", {})
                if tier == 0 and seasonal:
                    try:
                        for s_id, s_info in seasonal.items():
                            s_tier = s_info.get("CompetitiveTier", 0)
                            if s_tier > tier: 
                                tier = s_tier
                                kp = s_info.get("RankedRating", 0)
                    except: pass
                
                # 4. Yol: Peak Tier (Kariyer Zirve Derecesi)
                max_tier = tier
                if seasonal:
                    try:
                        for s_id, s_info in seasonal.items():
                            s_tier = s_info.get("CompetitiveTier", 0)
                            if s_tier > max_tier:
                                max_tier = s_tier
                            for t_str in (s_info.get("WinsByTier") or {}).keys():
                                try:
                                    t_int = int(t_str)
                                    if t_int > max_tier:
                                        max_tier = t_int
                                except: pass
                    except: pass

                self._tier_cache[puuid] = tier
                self._kp_cache[puuid] = kp
                if not hasattr(self, "_peak_tier_cache"):
                    self._peak_tier_cache = {}
                self._peak_tier_cache[puuid] = max_tier
                
                return RANK_NAMES.get(tier, "Unranked")
        except:
            pass
        return "[dim]Bilinmiyor[/dim]"



        
    def get_parties_from_presence(self):
        """Yerel Riot Client üzerinden party ve rank bilgilerini çek"""
        presence_map = {}
        try:
            auth = base64.b64encode(f"riot:{self.password}".encode()).decode()
            local_headers = {"Authorization": f"Basic {auth}"}
            
            # 0. /chat/v5/participants üzerinden katılımcı ve isim tespiti
            try:
                r_cp = self.session.get(f"{self.base_url}/chat/v5/participants", headers=local_headers, verify=False, timeout=1.5)
                if r_cp.status_code == 200:
                    for cp in r_cp.json().get("participants", []):
                        p_uid = cp.get("puuid")
                        p_gn = cp.get("game_name")
                        p_gt = cp.get("game_tag")
                        if p_uid and p_gn and p_gt:
                            c_fullname = f"{p_gn}#{p_gt}"
                            self.cache_name(p_uid, c_fullname)
                            if p_uid not in presence_map:
                                presence_map[p_uid] = {"name": c_fullname, "rank": 0, "level": 0, "party_id": ""}
                            else:
                                presence_map[p_uid]["name"] = c_fullname
            except Exception:
                pass

            # 1. /chat/v4/presences
            r = self.session.get(f"{self.base_url}/chat/v4/presences", headers=local_headers, verify=False)
            if r.status_code == 200:
                presences = r.json().get("presences", [])
                for p in presences:
                    puuid = p.get("puuid")
                    g_name = p.get("game_name")
                    g_tag = p.get("game_tag")
                    p_name = None
                    if g_name and g_tag:
                        p_name = f"{g_name}#{g_tag}"
                        if puuid and (puuid not in self._name_cache or self._name_cache[puuid] in ["Bilinmiyor", "#", "?#?", "None#None", "Unknown", ""]):
                            self._name_cache[puuid] = p_name

                    private_b64 = p.get("private")
                    if puuid and private_b64:
                        try:
                            decoded = json.loads(base64.b64decode(private_b64).decode())
                            rank = decoded.get("competitiveTier", 0)
                            if rank == 0: rank = decoded.get("rankedTier", 0)
                            if rank == 0: rank = decoded.get("rank", 0)
                            
                            # PARTY ID TESPİTİ (partyPresenceData ve varyasyonları)
                            p_pres = decoded.get("partyPresenceData") or {}
                            party_id = (
                                decoded.get("partyId")
                                or decoded.get("partyID")
                                or decoded.get("party_id")
                                or decoded.get("l_partyId")
                                or p_pres.get("partyId")
                                or p_pres.get("partyID")
                                or (decoded.get("matchPresenceData") or {}).get("partyId")
                                or ""
                            )
                            if party_id == "00000000-0000-0000-0000-000000000000":
                                party_id = ""

                            pres_lvl = decoded.get("accountLevel", 0)
                            if pres_lvl and pres_lvl > 0:
                                if not hasattr(self, "_level_cache"):
                                    self._level_cache = {}
                                self._level_cache[puuid] = pres_lvl
                                self._level_cache[f"lvl_{puuid}"] = pres_lvl

                            presence_map[puuid] = {
                                "name": p_name,
                                "rank": rank,
                                "level": pres_lvl,
                                "party_id": party_id
                            }
                        except: continue

            # (Eski /presence/v1/presences 404 verdiği için optimize edilerek kaldırıldı)

            return presence_map
        except:
            return presence_map

    def get_live_match_score(self, coregame_match_id=None):
        """Yerel Riot Client presence verisinden canlı maç skorunu, haritayı ve oyun modunu çek"""
        result = {
            "ally_score": 0,
            "enemy_score": 0,
            "map_name": "",
            "queue_id": "",
            "is_competitive": False,
            "state": "INGAME"
        }
        
        # 1. Öncelikle coregame_match_id varsa doğrudan coregame detayından haritayı ve modu al
        try:
            m_id = coregame_match_id or self.get_coregame()
            if m_id:
                c_details = self.get_coregame_details(m_id)
                if c_details:
                    map_id_raw = c_details.get("MapID", "")
                    if map_id_raw:
                        result["map_name"] = VAL_MAPS.get(map_id_raw, map_id_raw.split('/')[-1] if '/' in map_id_raw else "")
                    
                    # Queue ID kontrolü
                    q_id = c_details.get("MatchmakingData", {}).get("QueueID", "")
                    if not q_id:
                        q_id = c_details.get("QueueID", "")
                    if q_id:
                        result["queue_id"] = str(q_id).lower()
                        if "competitive" in result["queue_id"]:
                            result["is_competitive"] = True
        except:
            pass

        try:
            auth = base64.b64encode(f"riot:{self.password}".encode()).decode()
            local_headers = {"Authorization": f"Basic {auth}"}
            
            # /chat/v4/presences ve /presence/v1/presences üzerinden tara
            endpoints = [f"{self.base_url}/chat/v4/presences", f"{self.base_url}/presence/v1/presences"]
            found_presence = False
            for ep in endpoints:
                try:
                    r = self.session.get(ep, headers=local_headers, verify=False)
                    if r.status_code != 200:
                        continue
                    presences = r.json().get("presences", [])
                    for p in presences:
                        p_puuid = p.get("puuid")
                        if p_puuid and p_puuid == self.puuid:
                            priv_b64 = p.get("private")
                            if priv_b64:
                                decoded = json.loads(base64.b64decode(priv_b64).decode())
                                session_loop_state = decoded.get("sessionLoopState", "")
                                party_state = decoded.get("partyState", "")
                                p_score = decoded.get("partyOwnerMatchScoreAllyTeam", decoded.get("partyScore", 0))
                                e_score = decoded.get("partyOwnerMatchScoreEnemyTeam", 0)
                                map_path = decoded.get("matchMap", "")
                                queue_id_pres = decoded.get("queueId", decoded.get("matchQueueId", ""))
                                
                                if p_score is not None:
                                    result["ally_score"] = int(p_score)
                                if e_score is not None:
                                    result["enemy_score"] = int(e_score)

                                # Eğer coregame detayından harita bulunamadıysa presence mapPath'e bak
                                if not result["map_name"] and map_path:
                                    result["map_name"] = VAL_MAPS.get(map_path, map_path.split('/')[-1] if '/' in map_path else "")

                                if queue_id_pres:
                                    result["queue_id"] = str(queue_id_pres).lower()
                                    if "competitive" in result["queue_id"]:
                                        result["is_competitive"] = True
                                
                                found_presence = True
                                break
                    if found_presence:
                        break
                except:
                    pass
        except:
            pass
        return result

    def _detect_parties_from_history(self, puuids):
        """Kendi takımımızdaki oyuncuların son maç geçmişlerini çapraz eşleştirerek premade grupları tespit eder"""
        if not puuids or len(puuids) <= 1:
            return {}
        
        puuids = [str(p).strip() for p in puuids if p]
        
        def fetch_hist_matches(p):
            try:
                h_url = f"https://pd.{self.shard}.a.pvp.net/match-history/v1/history/{p}?startIndex=0&endIndex=10"
                hr = self.session.get(h_url, headers=self.get_headers(), verify=False, timeout=2.5)
                if hr.status_code == 200:
                    hist = hr.json().get("History", [])
                    return p, [h.get("MatchID") for h in hist if h.get("MatchID")]
            except Exception:
                pass
            return p, []

        with ThreadPoolExecutor(max_workers=min(5, len(puuids))) as ex:
            player_histories = dict(ex.map(fetch_hist_matches, puuids))

        shared_match_map = {}
        for p, m_list in player_histories.items():
            for mid in m_list:
                shared_match_map.setdefault(mid, set()).add(p)

        cand_matches = {mid: p_set for mid, p_set in shared_match_map.items() if len(p_set) > 1}
        if not cand_matches:
            return {p: "" for p in puuids}

        def fetch_match_details_json(mid):
            try:
                det_url = f"https://pd.{self.shard}.a.pvp.net/match-details/v1/matches/{mid}"
                dr = self.session.get(det_url, headers=self.get_headers(), verify=False, timeout=2.5)
                if dr.status_code == 200:
                    return mid, dr.json()
            except Exception:
                pass
            return mid, None

        with ThreadPoolExecutor(max_workers=min(8, len(cand_matches))) as ex:
            det_results = dict(ex.map(fetch_match_details_json, list(cand_matches.keys())))

        parent = {p: p for p in puuids}
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        for mid, djson in det_results.items():
            if not djson:
                continue
            for pl in djson.get("players", []):
                sub = pl.get("subject")
                lvl = pl.get("accountLevel", 0)
                if sub and lvl > 0:
                    if not hasattr(self, "_level_cache"): self._level_cache = {}
                    self._level_cache[f"lvl_{sub}"] = lvl

            match_parties = {}
            for pl in djson.get("players", []):
                sub = pl.get("subject")
                pid = pl.get("partyId")
                if sub and pid and pid != "00000000-0000-0000-0000-000000000000":
                    match_parties.setdefault(pid, []).append(sub)

            for pid, mems in match_parties.items():
                in_curr = [m for m in mems if m in parent]
                if len(in_curr) > 1:
                    first = in_curr[0]
                    for other in in_curr[1:]:
                        union(first, other)

        party_mapping = {}
        grouped = {}
        for p in puuids:
            r = find(p)
            grouped.setdefault(r, []).append(p)

        for root, mems in grouped.items():
            if len(mems) > 1:
                group_pid = f"history_group_{root[:8]}"
                for m in mems:
                    party_mapping[m] = group_pid
            else:
                party_mapping[mems[0]] = ""

        return party_mapping

    def get_all_players(self, match_id, match_type="pregame"):
        """Maçtaki tüm oyuncuları ve kendi takım arkadaşlarımızın parti (grup) bilgilerini al"""
        if match_type == "pregame":
            details = self.get_match_details(match_id)
            if not details:
                return None, None, None, None
            ally_team = details.get("AllyTeam", {})
            ally_list = ally_team.get("Players", [])
            enemy_team = details.get("EnemyTeam", {}) if "EnemyTeam" in details else {}
            enemy_list = enemy_team.get("Players", []) if enemy_team else []
        else:
            details = self.get_coregame_details(match_id)
            if not details:
                return None, None, None, None
            all_players_raw = details.get("Players", [])
            my_team = None
            for player in all_players_raw:
                p_sub = player.get("Subject") or player.get("subject") or player.get("puuid")
                if p_sub == self.puuid:
                    my_team = player.get("TeamID") or player.get("teamId")
                    break
            
            ally_list = []
            enemy_list = []
            for player in all_players_raw:
                t_id = player.get("TeamID") or player.get("teamId")
                if my_team and t_id == my_team:
                    ally_list.append(player)
                elif not my_team and (player.get("Subject") or player.get("subject") or player.get("puuid")) == self.puuid:
                    ally_list.append(player)
                else:
                    enemy_list.append(player)

        ally_puuids = [str(p.get("Subject") or p.get("subject") or p.get("puuid") or "").strip() for p in ally_list]
        ally_puuids = [p for p in ally_puuids if p]
        
        enemy_puuids = [str(p.get("Subject") or p.get("subject") or p.get("puuid") or "").strip() for p in enemy_list]
        enemy_puuids = [p for p in enemy_puuids if p]
        
        all_puuids = ally_puuids + enemy_puuids

        # 1. Aşama: Kullanıcının Kendi Partisi (GLZ Party Service - %100 Kesinlik)
        user_party_id = None
        user_party_members = set()
        try:
            p_self_url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/parties/v1/players/{self.puuid}"
            r_pself = self.session.get(p_self_url, headers=self.get_headers(), verify=False, timeout=2)
            if r_pself.status_code == 200:
                cur_pid = r_pself.json().get("CurrentPartyID")
                if cur_pid:
                    p_det_url = f"https://glz-{self.shard}-1.{self.shard}.a.pvp.net/parties/v1/parties/{cur_pid}"
                    r_pdet = self.session.get(p_det_url, headers=self.get_headers(), verify=False, timeout=2)
                    if r_pdet.status_code == 200:
                        mems = r_pdet.json().get("Members", [])
                        if len(mems) > 1:
                            user_party_id = cur_pid
                            for m in mems:
                                m_sub = m.get("Subject")
                                if m_sub:
                                    user_party_members.add(m_sub)
        except Exception:
            pass

        # 2. Aşama: Yerel Chat & Presences Parti Tespiti
        presence_data = self.get_parties_from_presence()
        try:
            r = self.session.get(f"{self.base_url}/chat/v6/conversations/ares-parties", headers=self.headers, verify=False, timeout=1.5)
            if r.status_code == 200:
                p_convs = r.json().get("conversations", [])
                for c in p_convs:
                    p_cid = c.get("cid") or c.get("id") or "party-chat"
                    raw_members = c.get("members", [])
                    cmembers = []
                    for m in raw_members:
                        if isinstance(m, dict):
                            puuid_c = m.get("puuid") or str(m.get("id", "")).split("@")[0]
                        elif isinstance(m, str):
                            puuid_c = m.split("@")[0]
                        else:
                            puuid_c = None
                        if puuid_c:
                            cmembers.append(puuid_c)
                    if len(cmembers) > 1:
                        for m_puuid in cmembers:
                            if m_puuid not in presence_data:
                                presence_data[m_puuid] = {"party_id": p_cid, "rank": 0}
                            else:
                                presence_data[m_puuid]["party_id"] = p_cid
        except Exception:
            pass

        # 3. Aşama: Sadece Kendi Takım Arkadaşlarımız İçin Geçmiş Maç Çapraz Eşleştirmesi
        history_parties = {}
        if len(ally_puuids) > 1:
            if not hasattr(self, "_match_parties_cache"):
                self._match_parties_cache = {}
            cached = self._match_parties_cache.get(match_id)
            if cached and all(p in cached for p in ally_puuids):
                history_parties = cached
            else:
                history_parties = self._detect_parties_from_history(ally_puuids)
                self._match_parties_cache[match_id] = history_parties

        # 4. Aşama: İsimleri toplu çek
        names_map = self.get_player_names(all_puuids)

        def process_player(player, is_ally=True):
            puuid = player.get("Subject") or player.get("subject") or player.get("puuid") or ""
            name = names_map.get(puuid, "Bilinmiyor")
            p_info = presence_data.get(puuid, {})

            # Parti tespiti SADECE kendi takımımız için yapılır
            raw_party_id = ""
            if is_ally:
                if puuid in user_party_members and user_party_id:
                    raw_party_id = user_party_id
                elif history_parties.get(puuid):
                    raw_party_id = history_parties[puuid]
                else:
                    raw_party_id = p_info.get("party_id", "")
                if raw_party_id == "00000000-0000-0000-0000-000000000000":
                    raw_party_id = ""

            presence_rank_tier = p_info.get("rank", 0)
            presence_kp = p_info.get("kp", 0)
            
            invalid_names = {"Bilinmiyor", "#", "?#?", "None#None", "Unknown", ""}
            if not name or name in invalid_names:
                if p_info.get("name") and p_info["name"] not in invalid_names:
                    name = p_info["name"]
                    self._name_cache[puuid] = name
                elif puuid in self._name_cache and self._name_cache[puuid] not in invalid_names:
                    name = self._name_cache[puuid]
            
            # Rank, KP ve Peak Rank (Kariyer Zirvesi) bilgisi
            kp = 0
            if not hasattr(self, "_peak_tier_cache"):
                self._peak_tier_cache = {}

            if puuid not in self._peak_tier_cache or puuid not in self._rank_cache:
                rank = self.get_player_rank(puuid)
                if rank == "[dim]Bilinmiyor[/dim]" and presence_rank_tier is not None:
                    rank = RANK_NAMES.get(presence_rank_tier, "Unranked")
                self._rank_cache[puuid] = rank
                presence_rank_tier = self._tier_cache.get(puuid, presence_rank_tier or 0)
                kp = self._kp_cache.get(puuid, 0)
            else:
                rank = self._rank_cache[puuid]
                presence_rank_tier = self._tier_cache.get(puuid, 0)
                kp = self._kp_cache.get(puuid, 0)

            peak_tier = self._peak_tier_cache.get(puuid, presence_rank_tier or 0)
            if peak_tier < (presence_rank_tier or 0):
                peak_tier = presence_rank_tier or 0
            peak_rank = RANK_NAMES.get(peak_tier, "Unranked")
            
            # Seviye ve Gizlilik tespiti
            p_ident = player.get("PlayerIdentity", {})
            is_incognito = bool(p_ident.get("Incognito") or player.get("Incognito"))
            hide_level = bool(p_ident.get("HideAccountLevel") or player.get("HideAccountLevel"))

            agent_uuid = player.get("CharacterID", "")
            agent_name = self.uuid_to_agent_name(agent_uuid)
            is_me = puuid == self.puuid
            team_id = player.get("TeamID") or player.get("teamId") or ""
            
            is_locked = player.get("CharacterSelectionState", "") == "locked"
            if match_type == "coregame":
                is_locked = True

            level = p_ident.get("AccountLevel", 0)
            if not level or level == 0:
                level = player.get("AccountLevel", 0)
            if (not level or level == 0) and p_info.get("level", 0) > 0:
                level = p_info.get("level")
            cache_key = f"lvl_{puuid}"
            if (not level or level == 0) and hasattr(self, "_level_cache"):
                level = self._level_cache.get(puuid) or self._level_cache.get(cache_key) or 0

            if level and level > 0:
                if not hasattr(self, "_level_cache"):
                    self._level_cache = {}
                self._level_cache[puuid] = level
                self._level_cache[cache_key] = level

            if (not name or name in invalid_names) and puuid in self._name_cache and self._name_cache[puuid] not in invalid_names:
                name = self._name_cache[puuid]

            is_hidden_name = False
            if is_incognito and not is_me:
                name = "Gizli"
                is_hidden_name = True
            elif not name or name in invalid_names or name.endswith("#???") or name.startswith("#"):
                name = "Gizli"
                is_hidden_name = True

            name_obj = {
                "tr": "Gizli" if is_hidden_name else name,
                "en": "Hidden" if is_hidden_name else name
            }

            return {
                "puuid": puuid,
                "name": name,
                "name_obj": name_obj,
                "is_hidden_name": is_hidden_name,
                "agent": agent_name,
                "agent_uuid": agent_uuid,
                "locked": is_locked,
                "level": str(level) if level else "0",
                "rank": rank,
                "kp": kp,
                "tier": presence_rank_tier,
                "peak_tier": peak_tier,
                "peak_rank": peak_rank,
                "is_me": is_me,
                "team_id": team_id,
                "party_id": raw_party_id,
                "is_incognito": is_incognito,
                "hide_level": hide_level
            }
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            ally_futures = [executor.submit(process_player, p, True) for p in ally_list]
            enemy_futures = [executor.submit(process_player, p, False) for p in enemy_list]
            ally_players = [f.result() for f in ally_futures]
            enemy_players = [f.result() for f in enemy_futures]

        # 5. Aşama: Sadece Kendi Takımımız İçin Premade Gruplaması
        party_members_map = {}
        for p_obj in ally_players:
            pid = p_obj.get("party_id")
            if pid and pid != "00000000-0000-0000-0000-000000000000":
                party_members_map.setdefault(pid, []).append(p_obj)

        party_idx = 1
        party_colors_palette = ['#8b5cf6', '#06b6d4', '#f59e0b', '#ec4899', '#10b981', '#3b82f6']
        
        sorted_parties = sorted(
            party_members_map.items(),
            key=lambda item: (0 if any(m.get("is_me") for m in item[1]) else 1, -len(item[1]))
        )

        for pid, members in sorted_parties:
            if len(members) > 1:
                p_label = f"GRP {party_idx}"
                p_color = party_colors_palette[(party_idx - 1) % len(party_colors_palette)]
                for m in members:
                    m["party_label"] = p_label
                    m["party_color"] = p_color
                    m["is_premade"] = True
                party_idx += 1
            else:
                for m in members:
                    m["party_label"] = "SOLO"
                    m["party_color"] = ""
                    m["is_premade"] = False

        for p_obj in ally_players:
            if "party_label" not in p_obj:
                p_obj["party_label"] = "SOLO"
                p_obj["party_color"] = ""
                p_obj["is_premade"] = False

        # Karşı takım için grup etiketleri tamamen boş ve devre dışıdır
        for p_obj in enemy_players:
            p_obj["party_label"] = ""
            p_obj["party_color"] = ""
            p_obj["is_premade"] = False

        map_id = details.get("MapID", "Bilinmiyor")
        map_name = VAL_MAPS.get(map_id, map_id.split('/')[-1] if '/' in map_id else "Bilinmiyor")
        
        return ally_players, enemy_players, party_members_map, map_name

    def get_match_players(self, match_id):
        """Maçtaki oyuncuları ve party bilgilerini al"""
        details = self.get_match_details(match_id)
        if not details:
            return None, None, None
        
        ally_players = []
        enemy_players = []
        
        # Party ID'lerini grupla
        party_colors = {}
        color_index = 0
        colors = ["🔴", "🟢", "🔵", "🟡", "🟣", "🟠"]
        
        def process_team(team_data, is_ally=True):
            players = []
            for player in team_data.get("Players", []):
                puuid = player.get("Subject", "")
                name = self.get_player_name(puuid)
                party_id = player.get("PartyID", "")
                agent_uuid = player.get("CharacterID", "")
                agent_name = self.uuid_to_agent_name(agent_uuid)
                is_locked = player.get("CharacterSelectionState", "") == "locked"
                is_me = puuid == self.puuid
                
                # Party rengi ata
                nonlocal color_index
                if party_id:
                    if party_id not in party_colors:
                        party_colors[party_id] = colors[color_index % len(colors)]
                        color_index += 1
                    party_indicator = party_colors[party_id]
                else:
                    party_indicator = "⚪"
                
                players.append({
                    "name": name,
                    "agent": agent_name,
                    "agent_uuid": agent_uuid,
                    "locked": is_locked,
                    "party": party_indicator,
                    "is_me": is_me,
                    "party_id": party_id
                })
            return players
        
        # Ally team
        ally_team = details.get("AllyTeam", {})
        ally_players = process_team(ally_team, is_ally=True)
        
        # Enemy team
        enemy_team = details.get("EnemyTeam", {})
        if enemy_team:
            enemy_players = process_team(enemy_team, is_ally=False)
        
        return ally_players, enemy_players, party_colors
    
    def uuid_to_agent_name(self, uuid):
        """UUID'den agent ismi bul"""
        if not uuid or uuid == "":
            return "SELECTING" # Base identifier
        
        for name, uid in AGENTS.items():
            if uid == uuid:
                return name
        return "UNKNOWN"


def get_banner():
    banner_text = """
[bold red]  ██╗   ██╗ █████╗ ██╗      ██████╗ [/bold red][white]██╗      ██████╗  ██████╗██╗  ██╗[/white]
[bold red]  ██║   ██║██╔══██╗██║     ██╔═══██╗[/bold red][white]██║     ██╔═══██╗██╔════╝██║ ██╔╝[/white]
[bold red]  ██║   ██║███████║██║     ██║   ██║[/bold red][white]██║     ██║   ██║██║     █████╔╝ [/white]
[bold red]  ╚██╗ ██╔╝██╔══██║██║     ██║   ██║[/bold red][white]██║     ██║   ██║██║     ██╔═██╗ [/white]
[bold red]   ╚████╔╝ ██║  ██║███████╗╚██████╔╝[/bold red][white]███████╗╚██████╔╝╚██████╗██║  ██╗[/white]
[bold red]    ╚═══╝  ╚═╝  ╚═╝╚══════╝ ╚═════╝ [/bold red][white]╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝[/white]
"""
    return Panel(
        Text.from_markup(banner_text),
        subtitle="[bold dim]PRO EDITION v1.1 - ULTRA LATENCY[/bold dim]",
        border_style="red",
        box=box.SQUARE,
        padding=(0, 2)
    )

def get_status_panel(locker=None):
    if not locker:
        status = "[red]●[/red] [dim]BAĞLI DEĞİL[/dim]"
    else:
        status = f"[green]●[/green] [bold white]AKTİF:[/bold white] [dim]{locker.puuid}[/dim]"
    return status

def show_agents():
    def get_role_table(agents, color):
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        for agent in agents:
            try:
                idx = list(AGENTS.keys()).index(agent) + 1
                t.add_row(f"[{color}]{idx:2}[/]", f"[white]{agent}[/]")
            except (ValueError, IndexError):
                pass
        return t

    duelists = [name for name, d in AGENT_DATA.items() if d.get("role") in ["Düellocu", "Duelist"]]
    sentinels = [name for name, d in AGENT_DATA.items() if d.get("role") in ["Gözcü", "Sentinel"]]
    initiators = [name for name, d in AGENT_DATA.items() if d.get("role") in ["Öncü", "Initiator"]]
    controllers = [name for name, d in AGENT_DATA.items() if d.get("role") in ["Kontrol Uzmanı", "Controller", "Kontrol"]]

    grid = Table.grid(expand=True)
    grid.add_column(ratio=1); grid.add_column(ratio=1); grid.add_column(ratio=1); grid.add_column(ratio=1)
    grid.add_row(
        Panel(get_role_table(duelists, "red"), title="[bold red]DÜELLOCU[/]", border_style="dim", box=box.SQUARE),
        Panel(get_role_table(sentinels, "green"), title="[bold green]GÖZCÜ[/]", border_style="dim", box=box.SQUARE),
        Panel(get_role_table(initiators, "blue"), title="[bold blue]ÖNCÜ[/]", border_style="dim", box=box.SQUARE),
        Panel(get_role_table(controllers, "magenta"), title="[bold magenta]KONTROL[/]", border_style="dim", box=box.SQUARE)
    )
    console.print(grid)


def show_main_menu(locker):
    """Sade ve Şık Ana Menü"""
    console.print(get_banner())
    
    menu = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    menu.add_row("[bold white]1.[/] [bold cyan]Ajan Kilitleme + Canlı Takip[/]", "[dim]OTOMATİK[/]")
    menu.add_row("[bold white]2.[/] [bold yellow]Sadece Oyuncu Bilgileri[/]", "[dim]İZLEME[/]")
    menu.add_row("[bold white]3.[/] [bold magenta]Anti-AFK Arka Plan Modu[/]", "[dim]BOT[/]")
    menu.add_row("[bold white]4.[/] [bold green]Skin Dedektörü (Vandal/Phantom)[/]", "[dim]YENİ[/]")
    menu.add_row("", "")
    menu.add_row("[bold red]0.[/] [bold red]Çıkış[/]", "")

    status = get_status_panel(locker)
    console.print(Panel(menu, title=status, title_align="right", border_style="dim", box=box.SQUARE))


def run_live_info_loop(locker, agent_name=None):
    """Oyun başlayana kadar oyuncu bilgilerini sürekli güncelle"""
    console.print()
    console.print("[dim]Oyuncu bilgileri oyun başlayana kadar güncellenecek...[/dim]")
    console.print("[dim italic]Çıkmak için CTRL+C[/dim italic]")
    console.print()
    
    party_cache = {} # Match boyunca party bilgisini tutacak
    game_started = False
    
    while True:
        try:
            # Pregame ve Coregame kontrolü
            pregame_match = locker.get_pregame()
            coregame_match = locker.get_coregame()
            
            match_id = pregame_match or coregame_match
            if not match_id:
                console.print("\n[bold yellow]Maç sona erdi.[/bold yellow]")
                break
            
            match_type = "pregame" if pregame_match else "coregame"
            players, enemies, party_colors, map_name = locker.get_all_players(match_id, match_type)
            
            if match_type == "coregame":
                game_started = True
                status_text = "[green]Oyun Başladı - Karşı Takım Görünür![/green]"
            else:
                status_text = "[yellow]Karakter Seçimi[/yellow]"
            
            # UI Render
            os.system('cls' if os.name == 'nt' else 'clear')
            console.print(get_banner())
            if agent_name:
                console.print(Panel(f"[bold green]� {agent_name} KİLİTLENDİ![/bold green]", border_style="green"))
            
            console.print(f"Harita: [bold cyan]{map_name}[/bold cyan] | Durum: {status_text}")
            console.print()
            
            if players:
                # Ally Table
                ally_table = Table(title="[bold green]TAKIM ARKADAŞLARIN[/bold green]", box=box.SQUARE, border_style="green")
                ally_table.add_column("GRUP", justify="center", width=8)
                ally_table.add_column("LVL", justify="center", width=5)
                ally_table.add_column("RANK", justify="center", min_width=12)
                ally_table.add_column("PEAK", justify="center", min_width=12)
                ally_table.add_column("Oyuncu", justify="left", min_width=20)
                ally_table.add_column("Ajan", justify="center", min_width=10)
                ally_table.add_column("Durum", justify="center", width=8)
                
                for p in players:
                    name_style = "[bold yellow]" if p["is_me"] else "[white]"
                    agent_disp = p["agent"] if p["agent"] != "Seçiyor..." else "[dim]Seçiyor...[/dim]"
                    if p["locked"] and agent_disp == "[dim]Seçiyor...[/dim]": agent_disp = "[dim italic]Ajan Gizli[/dim italic]"
                    status = "[green]OK[/green]" if p["locked"] else "[yellow]...[/yellow]"
                    
                    if p.get("is_premade") and p.get("party_label") and p.get("party_label") != "SOLO":
                        party_disp = f"[bold magenta]{p.get('party_label')}[/bold magenta]"
                    else:
                        party_disp = "[dim]SOLO[/dim]"
                    
                    peak_disp = p.get("peak_rank", "Unranked")
                    if peak_disp not in ["Unranked", "Bilinmiyor", "-"]:
                        if p.get("peak_tier", 0) > p.get("tier", 0):
                            peak_disp = f"[bold yellow]{peak_disp}[/bold yellow]"
                        else:
                            peak_disp = f"[gold1]{peak_disp}[/gold1]"
                    else:
                        peak_disp = "[dim]-[/dim]"
                    
                    if p.get("name") in ["Gizli", "Hidden"] or p.get("is_hidden_name") or (p.get("is_incognito") and not p.get("is_me")):
                        name_disp = "[dim italic]Gizli[/dim italic]"
                    else:
                        name_disp = f"{name_style}{p['name']}[/]"

                    lvl_disp = p.get("level", "0")
                    if not lvl_disp or lvl_disp in ["0", 0] or p.get("hide_level"):
                        lvl_disp = "[dim]-[/dim]"

                    ally_table.add_row(party_disp, lvl_disp, p["rank"], peak_disp, name_disp, agent_disp, status)
                console.print(ally_table)
                
                # Enemy Table
                if enemies or game_started:
                    console.print()
                    enemy_table = Table(title="[bold red]KARŞI TAKIM[/bold red]", box=box.SQUARE, border_style="red")
                    enemy_table.add_column("LVL", justify="center", width=5)
                    enemy_table.add_column("RANK", justify="center", min_width=12)
                    enemy_table.add_column("PEAK", justify="center", min_width=12)
                    enemy_table.add_column("Oyuncu", justify="left", min_width=20)
                    enemy_table.add_column("Ajan", justify="center", min_width=10)
                    enemy_table.add_column("Durum", justify="center", width=8)
                    
                    for p in (enemies or []):
                        agent_disp = p["agent"] if p["agent"] != "Seçiyor..." else "[dim]Seçiyor...[/dim]"
                        if (p["locked"] or game_started) and agent_disp == "[dim]Seçiyor...[/dim]": agent_disp = "[dim italic]Ajan Gizli[/dim italic]"
                        status = "[green]OK[/green]" if (p["locked"] or game_started) else "[yellow]...[/yellow]"
                        
                        peak_disp = p.get("peak_rank", "Unranked")
                        if peak_disp not in ["Unranked", "Bilinmiyor", "-"]:
                            if p.get("peak_tier", 0) > p.get("tier", 0):
                                peak_disp = f"[bold yellow]{peak_disp}[/bold yellow]"
                            else:
                                peak_disp = f"[gold1]{peak_disp}[/gold1]"
                        else:
                            peak_disp = "[dim]-[/dim]"
                        
                        if p.get("name") in ["Gizli", "Hidden"] or p.get("is_hidden_name") or (p.get("is_incognito") and not p.get("is_me")):
                            e_name_disp = "[dim italic]Gizli[/dim italic]"
                        else:
                            e_name_disp = f"[white]{p['name']}[/]"

                        e_lvl_disp = p.get("level", "0")
                        if not e_lvl_disp or e_lvl_disp in ["0", 0] or p.get("hide_level"):
                            e_lvl_disp = "[dim]-[/dim]"

                        enemy_table.add_row(e_lvl_disp, p["rank"], peak_disp, e_name_disp, agent_disp, status)
                    console.print(enemy_table)
            
            if game_started:
                console.print("\n[bold green]>>> Oyun başladı, bilgiler sabitlendi.[/bold green]")
                break
                
            time.sleep(1)
        except KeyboardInterrupt:
            break

def agent_lock_mode(locker):
    """Mod 1: Ajan Kilitleme + Bilgi"""
    os.system('cls' if os.name == 'nt' else 'clear')
    console.print(get_banner())
    show_agents()
    try:
        choice = console.input("\n[bold cyan]> Ajan numarasını girin: [/bold cyan]")
        agent_name = list(AGENTS.keys())[int(choice)-1]
        agent_uuid = AGENTS[agent_name]
    except:
        console.print("[bold red]✗ Geçersiz seçim![/bold red]")
        time.sleep(1); return

    console.print(Panel(f"[bold green][OK] Seçilen Ajan: {agent_name}[/bold green]\n[dim]Maç bekleniyor...[/dim]", border_style="green", box=box.SQUARE))
    
    last_match = None
    while True:
        try:
            match_id = locker.get_pregame()
            if match_id and match_id != last_match:
                locker.select_agent(match_id, agent_uuid)
                locker.lock_agent(match_id, agent_uuid)
                run_live_info_loop(locker, agent_name)
                console.input("\n[dim]Devam etmek için ENTER'a basın...[/dim]")
                return
            time.sleep(0.5)
        except KeyboardInterrupt: return

def player_info_mode(locker):
    """Mod 2: Sadece Oyuncu Bilgisi"""
    os.system('cls' if os.name == 'nt' else 'clear')
    console.print(get_banner())
    console.print(Panel("[bold yellow][BEKLEMEDE] MAÇ İZLEME MODU AKTİF[/bold yellow]\n[dim]Maç bulunduğunda bilgiler gösterilecek.[/dim]", border_style="yellow", box=box.SQUARE))
    
    last_match = None
    while True:
        try:
            match_id, mtype = locker.get_current_match()
            if match_id:
                run_live_info_loop(locker)
                console.input("\n[dim]Devam etmek için ENTER'a basın...[/dim]")
                return
            time.sleep(0.5)
        except KeyboardInterrupt: return

def anti_afk_mode():
    """Mod 3: Anti-AFK Modu (Arka plan desteği ile)"""
    os.system('cls' if os.name == 'nt' else 'clear')
    console.print(get_banner())
    
    info_panel = Panel(
        "[bold magenta]🛡️ ANTİ-AFK SİSTEMİ (PRO)[/bold magenta]\n\n"
        "[white]Bu mod, Valorant penceresi arkada olsa bile çalışacak şekilde tasarlandı.\n\n"
        "[bold cyan]ÖNEMLİ AYARLAR:[/bold cyan]\n"
        "1. Oyun [bold yellow]\"Pencereli Tam Ekran\"[/bold yellow] modunda olmalıdır.\n"
        "2. Görüntü Ayarları -> [bold yellow]\"Kısıtla: Arka Planda FPS\"[/bold yellow] AYARI [bold green]AÇIK[/bold green] VE [bold green]60[/bold green] OLMALIDIR.\n"
        "   (Eğer 1 FPS ise oyun arkadaki komutları işlemez)\n\n"
        "[dim]Program şu an doğrudan Valorant motoruna (Unreal Engine) komut gönderiyor.[/dim]",
        border_style="magenta",
        box=box.SQUARE,
        padding=(1, 2)
    )
    console.print(info_panel)
    console.print("[dim italic]Durdurmak için CTRL+C[/dim italic]\n")

    # Valorant penceresini bul
    hwnd = ctypes.windll.user32.FindWindowW(None, "VALORANT  ")
    if not hwnd:
        console.print("[bold yellow](!) VALORANT penceresi bulunamadı. Standart (Global) modda çalışıyor...[/bold yellow]")
        console.print("[dim](Not: Oyunun açık olduğundan ve pencereli modda olduğundan emin olun)[/dim]\n")

    # Hem VK hem ScanCode içeren eşleşmeler
    AFK_MAP = {
        'W': (0x57, 0x11),
        'A': (0x41, 0x1E),
        'S': (0x53, 0x1F),
        'D': (0x44, 0x20),
        'SPACE': (0x20, 0x39)
    }

    try:
        while True:
            # Rastgele bir hareket seç
            key_name = random.choice(list(AFK_MAP.keys()))
            vk, scan = AFK_MAP[key_name]
            
            if hwnd:
                # Arka plan modu (Scan code ile)
                send_key_background(hwnd, vk, scan)
                console.print(f"[dim][{time.strftime('%H:%M:%S')}] Arka planda hedef: {key_name} [OK][/dim]")
            else:
                # Standart mod (Global)
                press_key(KEYS[key_name])
                time.sleep(random.uniform(0.1, 0.3))
                release_key(KEYS[key_name])
                console.print(f"[dim][{time.strftime('%H:%M:%S')}] Global hareket: {key_name} [FALLBACK][/dim]")
            
            # Rastgele bekleme (5-12 saniye)
            wait_time = random.uniform(5, 12)
            time.sleep(wait_time)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Anti-AFK durduruldu.[/bold yellow]")
        time.sleep(1)

def skin_intel_mode(locker):
    """Mod 4: Skin Dedektörü"""
    os.system('cls' if os.name == 'nt' else 'clear')
    console.print(get_banner())

    if not SKIN_CACHE:
        if not fetch_skin_database():
            console.print("[bold red]Hatası: Skin veritabanı indirilemedi![/bold red]")
            time.sleep(2); return
        fetch_rank_assets()
        fetch_agent_assets() # Added agent assets

    console.print(Panel("[bold green]SKIN DEDEKTÖRÜ[/bold green]\n[dim]Maçtaki oyuncuların silah desenlerini analiz ediyor...[/dim]", border_style="green", box=box.SQUARE))


    target_weapons = {
        "9c82e19d-4575-0200-1a81-3eacf00cf872": "Vandal",
        "ee8e8d15-496b-07ac-e5f6-8fae5d4c7b1a": "Phantom",
        "a03b24d3-4319-996d-0f8c-94bbfba1dfc7": "Operator",
        "e336c6b8-418d-9340-d77f-7a9e4cfe0702": "Sheriff"
    }

    while True:
        try:
            match_id = locker.get_coregame()
            if not match_id:
                console.print("\n[bold yellow]Aktif bir maç (Coregame) bulunamadı veya maç bitti.[/bold yellow]")
                console.print("[dim]Bu mod sadece oyun içindeyken çalışır.[/dim]")
                console.input("\n[dim]Menüye dönmek için ENTER...[/dim]")
                return

            loadouts = locker.get_match_loadouts(match_id)
            players, enemies, _, _ = locker.get_all_players(match_id, "coregame")
            
            all_players = players + (enemies or [])
            
            # Map loadouts to players
            player_skins = {}
            for l in loadouts:
                if "Subject" in l:
                    player_skins[l["Subject"]] = l["Loadout"]

            # UI Oluştur
            os.system('cls' if os.name == 'nt' else 'clear')
            console.print(get_banner())
            
            # Helper to create consistent tables
            def create_skin_table(title, style):
                t = Table(title=title, box=box.SQUARE, border_style=style)
                t.add_column("Oyuncu", justify="left", min_width=15)
                t.add_column("Ajan", justify="center", width=10)
                t.add_column("Vandal", justify="left", min_width=20, style="cyan")
                t.add_column("Phantom", justify="left", min_width=20, style="magenta")
                t.add_column("Operator", justify="left", min_width=20, style="red")
                t.add_column("Sheriff", justify="left", min_width=20, style="gold1")
                return t

            ally_table = create_skin_table("[bold green]TAKIM ARKADAŞLARIN[/bold green]", "green")
            enemy_table = create_skin_table("[bold red]KARŞI TAKIM[/bold red]", "red")

            # Process both lists
            for target_table, p_list in [(ally_table, players), (enemy_table, enemies)]:
                if not p_list: continue
                
                for p in p_list:
                    puuid = p["puuid"]
                    name = f"[bold yellow]{p['name']}[/]" if p["is_me"] else f"[white]{p['name']}[/]"
                    
                    vandal = "-"
                    phantom = "-"
                    op = "-"
                    sheriff = "-"

                    if puuid in player_skins:
                        guns = player_skins[puuid]["Items"]
                        for gun_id, gun_data in guns.items():
                            if gun_id in target_weapons:
                                skin_name = "Standart"
                                try:
                                    # Skin Socket UUID (Doğru UUID: ...abc)
                                    skin_socket_uuid = "bcef87d6-209b-46c6-8b19-fbe40bd95abc"
                                    
                                    if "Sockets" in gun_data and skin_socket_uuid in gun_data["Sockets"]:
                                        socket_id = gun_data["Sockets"][skin_socket_uuid]["Item"]["ID"]
                                        skin_data = SKIN_CACHE.get(socket_id, "Standart")
                                        if isinstance(skin_data, dict):
                                            skin_name = skin_data.get("tr") or skin_data.get("name") or skin_data.get("en") or "Standart"
                                        else:
                                            skin_name = str(skin_data)
                                except:
                                    pass
                                
                                # İsim kısaltma
                                skin_name = str(skin_name).replace(" Standart", "")
                                
                                if target_weapons[gun_id] == "Vandal": vandal = skin_name
                                elif target_weapons[gun_id] == "Phantom": phantom = skin_name
                                elif target_weapons[gun_id] == "Operator": op = skin_name
                                elif target_weapons[gun_id] == "Sheriff": sheriff = skin_name
                    
                    target_table.add_row(name, p["agent"], vandal, phantom, op, sheriff)

            console.print(ally_table)
            console.print("\n")
            if enemies:
                console.print(enemy_table)
            else:
                console.print("[dim]Karşı takım bilgisi bekleniyor...[/dim]")
            console.print("\n[dim]Veriler 5 saniyede bir güncellenir. Çıkmak için CTRL+C[/dim]")
            time.sleep(5)

        except KeyboardInterrupt:
            return
        except Exception as e:
            console.print(f"[red]Beklenmedik hata: {e}[/red]")
            time.sleep(3)
            return


# ----------------- WEB SERVER LOGIC -----------------
web_locker = None
afk_thread_running = False

@app.route('/')
def index():
    return render_template_string(WEB_TEMPLATE)

@app.route("/api/debug_assets")
def debug_assets():
    return jsonify({
        "skin_cache_size": len(SKIN_CACHE),
        "weapon_assets_size": len(WEAPON_ASSETS),
        "weapon_assets": WEAPON_ASSETS,
        "rank_assets_size": len(RANK_ASSETS),
        "agent_assets_size": len(AGENT_ASSETS)
    })

@app.route('/api/data')
def get_data():
    global web_locker
    
    
    status = "Bağlı Değil"
    phase = "Bekleniyor"
    allies = []
    enemies = []
    map_name = None

    
    if web_locker and hasattr(web_locker, 'session'):
        status = f"Bağlı ({web_locker.region})"
        
        try:
            coregame = web_locker.get_coregame()
            pregame = web_locker.get_pregame()
            match_id = coregame or pregame # Priority to core-game for real-time map accuracy
            
            if match_id:
                match_type = "coregame" if coregame else "pregame"
                phase_key = "INGAME" if coregame else "PREGAME"
                phase = "Oyun Oynanıyor" if coregame else "Karakter Seçimi"
                
                # Use existing logic
                p, e, _, map_name = web_locker.get_all_players(match_id, match_type)
                
                
                # Skin Intel
                match_loadouts = {}
                if match_type == "pregame": match_loadouts = web_locker.get_pregame_loadouts(match_id)
                else: match_loadouts = web_locker.get_coregame_loadouts(match_id)
                
                # v24.1: Robust Ally Party Map (backend fallback)
                ally_party_ids = [player.get("party_id") for player in p if player.get("party_id")]

                import re
                def clean_skin_name(name):
                    if not name: return name
                    patterns = [
                        r'\s*\(?(\d+\.\s*)?([Ss]eviye|[Ll]evel|[Aa]şama)\s*\d*\)?',
                        r'\s*\(?[Ss]eviye\s*\d+\)?',
                        r'\s*\(?[Ll]evel\s*\d+\)?',
                        r'\s*\(?[Aa]şama\s*\d+\)?'
                    ]
                    for pat in patterns:
                        name = re.sub(pat, '', name)
                    return name.strip()

                ALL_WEAPONS_DEF = [
                    # Yakın Dövüş (Bıçak en üstte)
                    {"prefixes": ["2f59173c"], "name": "Bıçak", "name_en": "Melee", "cat": "melee", "cat_name": "Yakın Dövüş", "cat_name_en": "Melee"},
                    # Tüfekler
                    {"prefixes": ["9c82e19d"], "name": "Vandal", "name_en": "Vandal", "cat": "rifle", "cat_name": "Tüfek", "cat_name_en": "Rifle"},
                    {"prefixes": ["ee8e8d15"], "name": "Phantom", "name_en": "Phantom", "cat": "rifle", "cat_name": "Tüfek", "cat_name_en": "Rifle"},
                    {"prefixes": ["8db0a1bf"], "name": "Warden", "name_en": "Warden", "cat": "rifle", "cat_name": "Tüfek", "cat_name_en": "Rifle"},
                    {"prefixes": ["ae3de142"], "name": "Bulldog", "name_en": "Bulldog", "cat": "rifle", "cat_name": "Tüfek", "cat_name_en": "Rifle"},
                    {"prefixes": ["4ade7faa"], "name": "Guardian", "name_en": "Guardian", "cat": "rifle", "cat_name": "Tüfek", "cat_name_en": "Rifle"},
                    # Tabancalar
                    {"prefixes": ["29a0cfab"], "name": "Classic", "name_en": "Classic", "cat": "sidearm", "cat_name": "Tabanca", "cat_name_en": "Sidearm"},
                    {"prefixes": ["1baa85b4"], "name": "Ghost", "name_en": "Ghost", "cat": "sidearm", "cat_name": "Tabanca", "cat_name_en": "Sidearm"},
                    {"prefixes": ["e336c6b8"], "name": "Sheriff", "name_en": "Sheriff", "cat": "sidearm", "cat_name": "Tabanca", "cat_name_en": "Sidearm"},
                    {"prefixes": ["44d4e95c", "44d4a956"], "name": "Frenzy", "name_en": "Frenzy", "cat": "sidearm", "cat_name": "Tabanca", "cat_name_en": "Sidearm"},
                    {"prefixes": ["42da8ccc", "42da8cee"], "name": "Shorty", "name_en": "Shorty", "cat": "sidearm", "cat_name": "Tabanca", "cat_name_en": "Sidearm"},
                    # Keskin Nişancı
                    {"prefixes": ["a03b24d3"], "name": "Operator", "name_en": "Operator", "cat": "sniper", "cat_name": "Keskin Nişancı", "cat_name_en": "Sniper"},
                    {"prefixes": ["5f0aaf7a", "5f0aaf3a"], "name": "Outlaw", "name_en": "Outlaw", "cat": "sniper", "cat_name": "Keskin Nişancı", "cat_name_en": "Sniper"},
                    {"prefixes": ["c4883e50"], "name": "Marshal", "name_en": "Marshal", "cat": "sniper", "cat_name": "Keskin Nişancı", "cat_name_en": "Sniper"},
                    # Hafif Makineli
                    {"prefixes": ["462080d1", "46982852"], "name": "Spectre", "name_en": "Spectre", "cat": "smg", "cat_name": "Hafif Makineli", "cat_name_en": "SMG"},
                    {"prefixes": ["f7e1b454"], "name": "Stinger", "name_en": "Stinger", "cat": "smg", "cat_name": "Hafif Makineli", "cat_name_en": "SMG"},
                    # Pompalı
                    {"prefixes": ["ec845bf4", "ec84293c"], "name": "Judge", "name_en": "Judge", "cat": "shotgun", "cat_name": "Pompalı", "cat_name_en": "Shotgun"},
                    {"prefixes": ["910be174"], "name": "Bucky", "name_en": "Bucky", "cat": "shotgun", "cat_name": "Pompalı", "cat_name_en": "Shotgun"},
                    # Ağır Silahlar
                    {"prefixes": ["63e6c2b6"], "name": "Odin", "name_en": "Odin", "cat": "heavy", "cat_name": "Ağır Silah", "cat_name_en": "Heavy"},
                    {"prefixes": ["55d8a0f4"], "name": "Ares", "name_en": "Ares", "cat": "heavy", "cat_name": "Ağır Silah", "cat_name_en": "Heavy"},
                ]

                def enrich_with_skins(player_list):
                    res = []
                    for player in (player_list or []):
                        # Rank/Tier processing
                        tier_id = player.get("tier", 0)
                        try: tier_id = int(tier_id)
                        except: tier_id = 0
                        
                        if tier_id == 0 and player.get("rank"):
                            rank_map = {"Demir": 3, "Bronz": 6, "Gümüş": 9, "Altın": 12, "Platin": 15, "Elmas": 18, "Yüce": 21, "İmmo": 24, "Ölümsüz": 24, "Radyant": 27}
                            r_name = player.get("rank", "").strip()
                            for k, v in rank_map.items():
                                if k in r_name:
                                    num = "".join(filter(str.isdigit, r_name))
                                    tier_id = v + (int(num)-1 if num else 0); break

                        # Agent processing
                        a_name = player.get("agent", "SELECTING")
                        a_obj = {"tr": "Seçiyor...", "en": "Selecting..."}
                        if a_name != "SELECTING" and a_name != "UNKNOWN":
                            a_obj = {"tr": a_name, "en": a_name}
                        
                        peak_tier_id = player.get("peak_tier", 0) or tier_id
                        try: peak_tier_id = int(peak_tier_id)
                        except: peak_tier_id = tier_id
                        if peak_tier_id < tier_id:
                            peak_tier_id = tier_id

                        p_data = {
                            "puuid": player.get("puuid"),
                            "rank": player.get("rank"),
                            "rank_obj": {"tr": RANK_NAMES.get(tier_id, "Bilinmiyor"), "en": RANK_NAMES_EN.get(tier_id, "Unknown")},
                            "kp": player.get("kp", 0),
                            "peak_tier": peak_tier_id,
                            "peak_rank": RANK_NAMES.get(peak_tier_id, "Unranked"),
                            "peak_rank_obj": {"tr": RANK_NAMES.get(peak_tier_id, "Bilinmiyor"), "en": RANK_NAMES_EN.get(peak_tier_id, "Unknown")},
                            "peak_rank_image": RANK_ASSETS.get(peak_tier_id, ""),
                            "name": player.get("name"), 
                            "name_obj": player.get("name_obj") or {"tr": player.get("name", "Gizli"), "en": "Hidden" if (player.get("name") in ["Gizli", "Unknown", "Bilinmiyor"] or player.get("is_incognito")) else player.get("name", "Hidden")},
                            "is_hidden_name": player.get("is_hidden_name", False) or player.get("name") in ["Gizli", "Unknown", "Bilinmiyor"],
                            "agent_obj": a_obj,
                            "agent": a_name,
                            "agent_uuid": player.get("agent_uuid"), "level": player.get("level"),
                            "agent_image": AGENT_ASSETS.get(a_name, ""),
                            "rank_image": RANK_ASSETS.get(tier_id, ""),
                            "is_me": player.get("is_me"), "locked": player.get("locked"),
                            "party_id": player.get("party_id", ""),
                            "party_label": player.get("party_label", "SOLO"),
                            "party_color": player.get("party_color", ""),
                            "is_premade": player.get("is_premade", False),
                            "is_incognito": player.get("is_incognito", False),
                            "hide_level": player.get("hide_level", False),
                            "vandal": "-", "vandal_img": "", "phantom": "-", "phantom_img": "",
                            "ghost": "-", "ghost_img": "", "op": "-", "op_img": "", "sheriff": "-", "sheriff_img": "",
                            "all_weapons": [],
                            "premium_count": 0
                        }

                        # Loadout Logic
                        puuid_lower = (player.get("puuid") or "").lower()
                        loadout = next((v for k, v in match_loadouts.items() if k and k.lower() == puuid_lower), None)
                        if not loadout and player.get("agent") in AGENTS:
                            a_uuid = AGENTS[player["agent"]].lower()
                            loadout = next((v for k, v in match_loadouts.items() if k and k.lower() == a_uuid), None)

                        items_map = {}
                        if loadout:
                            items = loadout.get("Guns") or loadout.get("Items") or {}
                            if isinstance(items, list):
                                items_map = {str(g.get("ID", "")).lower(): g for g in items}
                            elif isinstance(items, dict):
                                items_map = {str(k).lower(): v for k, v in items.items()}

                        player_weapons = []
                        premium_count = 0

                        for w_def in ALL_WEAPONS_DEF:
                            primary_prefix = w_def["prefixes"][0]
                            default_icon = WEAPON_ASSETS.get(primary_prefix, "")
                            f_skin = {"tr": "Standart", "en": "Standard", "icon": default_icon}
                            is_prem = False

                            # Silah verisini bul
                            g_data = None
                            matched_prefix = primary_prefix
                            for pfx in w_def["prefixes"]:
                                for item_id_lower, d in items_map.items():
                                    if item_id_lower.startswith(pfx):
                                        g_data = d
                                        matched_prefix = pfx
                                        break
                                if g_data:
                                    break

                            if g_data:
                                # 1. Socket kontrolü
                                for s_val in g_data.get("Sockets", {}).values():
                                    sid = s_val.get("Item", {}).get("ID", "").lower()
                                    if sid in SKIN_CACHE:
                                        sc = SKIN_CACHE[sid]
                                        tr_name = sc.get("tr") or sc.get("name") or "Standart"
                                        en_name = sc.get("en") or sc.get("name") or "Standard"
                                        f_skin = {"tr": tr_name, "en": en_name, "icon": sc.get("icon", "")}
                                        if not sid.startswith(matched_prefix):
                                            is_prem = True
                                        break

                                # 2. SkinID Fallback
                                if not is_prem and "SkinID" in g_data:
                                    sid = g_data["SkinID"].lower()
                                    if sid in SKIN_CACHE:
                                        sc = SKIN_CACHE[sid]
                                        tr_name = sc.get("tr") or sc.get("name") or "Standart"
                                        en_name = sc.get("en") or sc.get("name") or "Standard"
                                        f_skin = {"tr": tr_name, "en": en_name, "icon": sc.get("icon", "")}
                                        if not sid.startswith(matched_prefix):
                                            is_prem = True

                            # Temizleme ve override
                            f_skin["tr"] = clean_skin_name(f_skin.get("tr", ""))
                            f_skin["en"] = clean_skin_name(f_skin.get("en", ""))
                            
                            en_upper = f_skin.get("en", "").upper()
                            is_standard = any(kw in en_upper for kw in ["STANDARD", "STANDART"]) or en_upper == w_def["name_en"].upper()
                            
                            if is_standard:
                                is_prem = False
                                f_skin["tr"] = "Standart"
                                f_skin["en"] = "Standard"
                                f_skin["icon"] = default_icon or f_skin.get("icon", "")
                            elif not f_skin.get("icon"):
                                f_skin["icon"] = default_icon

                            if is_prem:
                                premium_count += 1

                            w_obj = {
                                "name": w_def["name"],
                                "name_en": w_def["name_en"],
                                "category": w_def["cat"],
                                "category_name": w_def["cat_name"],
                                "category_name_en": w_def["cat_name_en"],
                                "skin_name": f_skin["tr"],
                                "skin_name_en": f_skin["en"],
                                "icon": heal_url(f_skin["icon"]),
                                "is_premium": is_prem
                            }
                            player_weapons.append(w_obj)

                            # Ana ekrandaki 5 sütun için geriye dönük uyumluluk
                            w_en = w_def["name_en"]
                            if w_en == "Vandal":
                                p_data["vandal_obj"] = f_skin; p_data["vandal_img"] = heal_url(f_skin["icon"])
                            elif w_en == "Phantom":
                                p_data["phantom_obj"] = f_skin; p_data["phantom_img"] = heal_url(f_skin["icon"])
                            elif w_en == "Ghost":
                                p_data["ghost_obj"] = f_skin; p_data["ghost_img"] = heal_url(f_skin["icon"])
                            elif w_en == "Operator":
                                p_data["op_obj"] = f_skin; p_data["op_img"] = heal_url(f_skin["icon"])
                            elif w_en == "Sheriff":
                                p_data["sheriff_obj"] = f_skin; p_data["sheriff_img"] = heal_url(f_skin["icon"])

                        p_data["all_weapons"] = player_weapons
                        p_data["premium_count"] = premium_count

                        res.append(p_data)
                    return res


                
                allies = enrich_with_skins(p)
                enemies = enrich_with_skins(e)
        except: pass


    return jsonify({
        "status": status,
        "phase": phase,
        "phase_key": phase_key if 'phase_key' in locals() else "WAITING",
        "allies": allies,
        "enemies": enemies,
        "map": map_name
    })

@app.route('/api/agents')
def get_agents():
    global AGENT_DATA
    if not AGENT_DATA:
        fetch_agent_database()
        
    # Gruba göre paketle
    grouped = {}
    for name, info in AGENT_DATA.items():
        role = info["role"]
        if role not in grouped: grouped[role] = []
        grouped[role].append({"name": name, "icon": info["icon"]})
    
    # Rolleri sıralı döndür (Opsiyonel)
    return jsonify(grouped)

TARGET_LOCK_AGENT = None
LOCK_WORKER_RUNNING = False
LOCK_MUTEX = threading.Lock()

def _auto_lock_worker():
    global LOCK_WORKER_RUNNING, TARGET_LOCK_AGENT
    console.print("[bold green]WEB: Otomatik ajan kilitleme servisi devrede.[/bold green]")
    while LOCK_WORKER_RUNNING:
        try:
            target = TARGET_LOCK_AGENT
            if not target or not web_locker:
                time.sleep(0.5)
                continue

            pregame = web_locker.get_pregame()
            if pregame:
                if target in AGENTS:
                    agent_uuid = AGENTS[target]
                    web_locker.select_agent(pregame, agent_uuid)
                    success = web_locker.lock_agent(pregame, agent_uuid)
                    if success:
                        console.print(f"[bold green]WEB: {target} BAŞARIYLA KİLİTLENDİ![/bold green]")
                        TARGET_LOCK_AGENT = None
                        time.sleep(4)
            time.sleep(0.3)
        except Exception:
            time.sleep(1)

@app.route('/api/lock/<agent_name>')
def lock_agent(agent_name):
    global web_locker, TARGET_LOCK_AGENT, LOCK_WORKER_RUNNING
    if not web_locker: return jsonify({"status": "error", "msg": "Not connected"})
    
    TARGET_LOCK_AGENT = agent_name
    with LOCK_MUTEX:
        if not LOCK_WORKER_RUNNING:
            LOCK_WORKER_RUNNING = True
            threading.Thread(target=_auto_lock_worker, daemon=True).start()

    console.print(f"[bold cyan]WEB: Kilit hedefi güncellendi -> {agent_name}[/bold cyan]")
    return jsonify({"status": "ok", "msg": f"{agent_name} ARANIYOR..."})

def _afk_worker():
    global afk_thread_running
    import time
    keys = [0x57, 0x41, 0x53, 0x44, 0x20] # W, A, S, D, Space
    console.print("[green]WEB AFK BAŞLATILDI[/green]")
    while afk_thread_running:
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "VALORANT  ")
            if hwnd:
                k = random.choice(keys)
                ctypes.windll.user32.PostMessageW(hwnd, 0x0100, k, 0)
                time.sleep(random.uniform(0.1, 0.5))
                ctypes.windll.user32.PostMessageW(hwnd, 0x0101, k, 0)
            time.sleep(random.uniform(5, 15))
        except: pass

@app.route('/api/afk/<state>')
def set_afk(state):
    global afk_thread_running
    if state == 'on':
        if not afk_thread_running:
            afk_thread_running = True
            threading.Thread(target=_afk_worker, daemon=True).start()
    else:
        afk_thread_running = False
    return jsonify({"status": "ok", "msg": state})

def run_web_mode():
    global web_locker, SKIN_CACHE, RANK_ASSETS, AGENT_ASSETS, WEAPON_ASSETS
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # ========== DUAL-LANGUAGE SKIN LOADING (TR & EN) ==========
    console.print("[yellow]Skin veritabanı yükleniyor (TR & EN)...[/yellow]")
    try:
        SKIN_CACHE = {}  # FORCE RESET
        # Fetch TR & EN concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            f_tr = executor.submit(requests.get, "https://valorant-api.com/v1/weapons/skins", params={"language": "tr-TR"}, timeout=20)
            f_en = executor.submit(requests.get, "https://valorant-api.com/v1/weapons/skins", params={"language": "en-US"}, timeout=20)
            r_tr = f_tr.result()
            r_en = f_en.result()
        
        if r_tr.status_code == 200 and r_en.status_code == 200:
            data_tr = r_tr.json().get("data", [])
            data_en = r_en.json().get("data", [])
            
            # Map EN by UUID for quick lookup
            en_map = {s.get("uuid").lower(): s for s in data_en}
            
            for skin_tr in data_tr:
                uuid = skin_tr.get("uuid", "").lower()
                skin_en = en_map.get(uuid, {})
                
                name_tr = skin_tr.get("displayName")
                name_en = skin_en.get("displayName") or name_tr
                icon = heal_url(skin_tr.get("displayIcon"))
                
                levels_tr = skin_tr.get("levels", [])
                levels_en = skin_en.get("levels", [])
                chromas_tr = skin_tr.get("chromas", [])
                chromas_en = skin_en.get("chromas", [])

                # Icon fallback logic
                if not icon:
                    for lvl in levels_tr:
                        icon = heal_url(lvl.get("displayIcon") or lvl.get("fullRender"))
                        if icon: break
                
                if uuid: 
                    SKIN_CACHE[uuid] = {"tr": name_tr, "en": name_en, "icon": icon}
                
                # Cache levels (Use base name instead of level-specific name)
                en_levels_map = {l.get("uuid").lower(): l for l in levels_en}
                for lvl_tr in levels_tr:
                    l_uuid = lvl_tr.get("uuid", "").lower()
                    if l_uuid:
                        SKIN_CACHE[l_uuid] = {"tr": name_tr, "en": name_en, "icon": heal_url(lvl_tr.get("displayIcon")) or icon}

                # Cache chromas (Use base name instead of chroma-specific name)
                en_chromas_map = {c.get("uuid").lower(): c for c in chromas_en}
                for chr_tr in chromas_tr:
                    c_uuid = chr_tr.get("uuid", "").lower()
                    if c_uuid:
                        SKIN_CACHE[c_uuid] = {"tr": name_tr, "en": name_en, "icon": heal_url(chr_tr.get("displayIcon")) or icon}
            
            console.print(f"[green]DUAL-SKIN CACHE: {len(SKIN_CACHE)} item yüklendi![/green]")
        else:
            console.print("[red]Skin API hatası (TR veya EN)[/red]")
    except Exception as e:
        console.print(f"[red]Skin yükleme hatası: {e}[/red]")
    
    # WEAPON ASSETS (v44.8 Precision Sync)
    if not WEAPON_ASSETS:
        try:
            r = requests.get("https://valorant-api.com/v1/weapons", timeout=5)
            if r.status_code == 200:
                for w in r.json().get("data", []):
                    w_uuid = w.get("uuid", "").lower()
                    if w_uuid:
                        prefix = w_uuid[:8] # First 8 chars for prefix matching
                        WEAPON_ASSETS[prefix] = heal_url(w.get("displayIcon"))
            console.print(f"[green]WEAPON ASSETS: {len(WEAPON_ASSETS)} silah yüklendi![/green]")
        except: pass

    # RANK ASSETS
    if not RANK_ASSETS:
        try:
            r = requests.get("https://valorant-api.com/v1/competitivetiers", timeout=5)
            if r.status_code == 200:
                for episode in reversed(r.json().get("data", [])):
                    tiers = episode.get("tiers", [])
                    if len(tiers) > 5:
                        for tier in tiers:
                            icon = tier.get("largeIcon") or tier.get("smallIcon")
                            if tier.get("tier") is not None and icon:
                                RANK_ASSETS[tier.get("tier")] = icon
                        break
        except: pass
    
    # AGENT ASSETS & DATABASE (v45.0 Auto-Sync)
    if not AGENT_DATA:
        fetch_agent_database()

    # AGENT ASSETS Fallback
    if not AGENT_ASSETS:
        try:
            r = requests.get("https://valorant-api.com/v1/agents", params={"isPlayableCharacter": "true"}, timeout=5)
            if r.status_code == 200:
                for agent in r.json().get("data", []):
                    AGENT_ASSETS[agent.get("displayName")] = heal_url(agent.get("displayIcon"))
        except: pass
    
    from rich.table import Table
    from rich.align import Align
    
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # ASCII Header (Centered)
    ascii_text = """[bold red]
  ██╗   ██╗ █████╗ ██╗      ██████╗     ██╗      ██████╗  ██████╗██╗  ██╗███████╗██████╗ 
  ██║   ██║██╔══██╗██║     ██╔═══██╗    ██║     ██╔═══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
  ██║   ██║███████║██║     ██║   ██║    ██║     ██║   ██║██║     █████╔╝ █████╗  ██████╔╝
  ╚██╗ ██╔╝██╔══██║██║     ██║   ██║    ██║     ██║   ██║██║     ██╔═██╗ ██╔══╝  ██╔══██╗
   ╚████╔╝ ██║  ██║███████╗╚██████╔╝    ███████╗╚██████╔╝╚██████╗██║  ██╗███████╗██║  ██║
[/bold red]"""
    console.print(Align.center(ascii_text))

    # Modern Informative Pro Table
    status_table = Table(box=box.ROUNDED, border_style="cyan", show_header=False, expand=True)
    status_table.add_column("Key", style="bold cyan", width=14)
    status_table.add_column("Val", style="bold white")
    
    status_table.add_row("DURUM", "[bold green]● ÇEVRİMİÇİ / HAZIR[/bold green]")
    status_table.add_row("WEB ARAYÜZÜ", "[bold underline cyan]http://127.0.0.1:5000[/bold underline cyan]")
    status_table.add_row("VERİTABANI", f"[white]{len(SKIN_CACHE)}[/white] [dim]Silah Skini[/dim]  |  [white]{len(AGENT_ASSETS)}[/white] [dim]Ajan[/dim]")
    status_table.add_row("DISCORD RPC", "[bold green]● AKTİF (KepsLocker)[/bold green]" if PYPRESENCE_AVAILABLE else "[yellow]○ KAPALI (Kütüphane Eksik)[/yellow]")
    status_table.add_row("MOTOR", "[bold magenta]KEPSLOCK PRO ULTRA-LATENCY[/bold magenta]")

    console.print(Align.center(Panel(status_table, title="[bold white]SİSTEM DURUMU[/bold white]", border_style="bright_black", expand=False)))
    console.print(Align.center("[dim italic]Tarayıcınız otomatik açılıyor... Valorant lobisi bekleniyor...[/dim italic]\n"))

    def valo_checker():
        global web_locker
        while True:
            try:
                lockfile = get_lockfile()
                if lockfile:
                    port_changed = web_locker and getattr(web_locker, 'port', None) != lockfile.get('port')
                    if not web_locker or not getattr(web_locker, 'puuid', None) or port_changed:
                        temp_locker = Locker(lockfile)
                        if temp_locker.connect():
                            web_locker = temp_locker
                else:
                    web_locker = None
            except: 
                web_locker = None
            time.sleep(3)
            
    def discord_rpc_worker():
        global DISCORD_RPC
        if not PYPRESENCE_AVAILABLE:
            return
        
        while True:
            try:
                if not DISCORD_RPC:
                    try:
                        DISCORD_RPC = Presence(DISCORD_CLIENT_ID)
                        DISCORD_RPC.connect()
                    except Exception:
                        DISCORD_RPC = None
                        time.sleep(10)
                        continue

                # Discord Presence Durumunu Belirle
                details_text = "Valorant InstaLocker"
                state_text = "Panel Açık // Hazır"
                large_text = "Valorant InstaLocker PRO"
                large_img = "https://raw.githubusercontent.com/Keplorions/Valorant-InstaLocker/main/media/logo.png"

                if web_locker:
                    try:
                        core = web_locker.get_coregame()
                        preg = web_locker.get_pregame()
                        if core:
                            # Canlı Skor ve Harita Çekimi
                            score_info = web_locker.get_live_match_score(core)
                            m_name = score_info.get("map_name") if score_info else ""
                            a_sc = score_info.get("ally_score", 0) if score_info else 0
                            e_sc = score_info.get("enemy_score", 0) if score_info else 0
                            is_comp = score_info.get("is_competitive", False) if score_info else False
                            
                            # Detay Satırı: Harita Adı
                            if m_name and m_name != "Bilinmiyor":
                                details_text = f"Harita: {m_name}"
                            else:
                                details_text = "Maçta"

                            # Durum Satırı: Sadece Rekabetçi modunda canlı skor göster
                            if is_comp:
                                state_text = f"Skor: {a_sc} - {e_sc}"
                            else:
                                state_text = "Maç Oynanıyor"
                        elif preg:
                            # Ajan seçim ekranında harita tespiti
                            p_details = web_locker.get_match_details(preg)
                            preg_map = ""
                            if p_details and "MapID" in p_details:
                                m_id_raw = p_details["MapID"]
                                preg_map = VAL_MAPS.get(m_id_raw, m_id_raw.split('/')[-1] if '/' in m_id_raw else "")
                            
                            if preg_map and preg_map != "Bilinmiyor":
                                details_text = f"Harita: {preg_map}"
                            else:
                                details_text = "Ajan Seçim Ekranı"
                            state_text = "Ajan Seçiliyor..."
                        else:
                            details_text = "Lobide // Menüde"
                            state_text = "Valorant Bağlandı"
                    except Exception:
                        pass

                buttons = [
                    {"label": "Discord Sunucusu", "url": "https://discord.gg/93DSqGVXa2"},
                    {"label": "GitHub Projesi", "url": "https://github.com/Keplorions/Valorant-InstaLocker"}
                ]

                DISCORD_RPC.update(
                    details=details_text,
                    state=state_text,
                    start=RPC_START_TIME,
                    large_image=large_img,
                    large_text=large_text,
                    buttons=buttons
                )
            except Exception:
                try:
                    if DISCORD_RPC:
                        DISCORD_RPC.close()
                except Exception:
                    pass
                DISCORD_RPC = None
            
            time.sleep(15)

    threading.Thread(target=discord_rpc_worker, daemon=True).start()
    threading.Thread(target=valo_checker, daemon=True).start()
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def main():
    os.system('chcp 65001 > nul')

    # ========== BAŞLATMA MODU SEÇİM EKRANI ==========
    os.system('cls' if os.name == 'nt' else 'clear')
    ascii_text = """[bold red]
  ██╗   ██╗ █████╗ ██╗      ██████╗     ██╗      ██████╗  ██████╗██╗  ██╗███████╗██████╗ 
  ██║   ██║██╔══██╗██║     ██╔═══██╗    ██║     ██╔═══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
  ██║   ██║███████║██║     ██║   ██║    ██║     ██║   ██║██║     █████╔╝ █████╗  ██████╔╝
  ╚██╗ ██╔╝██╔══██║██║     ██║   ██║    ██║     ██║   ██║██║     ██╔═██╗ ██╔══╝  ██╔══██╗
   ╚████╔╝ ██║  ██║███████╗╚██████╔╝    ███████╗╚██████╔╝╚██████╗██║  ██╗███████╗██║  ██║
[/bold red]"""
    console.print(Align.center(ascii_text))

    menu_table = Table(box=box.ROUNDED, border_style="bright_black", show_header=False, expand=True)
    menu_table.add_column("No", style="bold cyan", width=5, justify="center")
    menu_table.add_column("Mod", style="bold white", width=26)
    menu_table.add_column("Açıklama", style="dim")

    menu_table.add_row(
        "[1]",
        "[bold green]NORMAL MOD[/bold green]",
        "Normal Valorant oturumu + Web Paneli (Ajan kilitleme, skin/rank takibi aktif)."
    )
    menu_table.add_row(
        "[2]",
        "[bold red]ÇEVRİMDIŞI MOD + PANEL[/bold red]\n[dim](KEPSLOCK Stealth)[/dim]",
        "KEPSLOCK motoru ile Valorant açılır (Çevrimdışı) + Web Paneli ve tüm özellikler aktif."
    )
    menu_table.add_row(
        "[3]",
        "[bold yellow]SADECE ÇEVRİMDIŞI MOD[/bold yellow]\n[dim](Web Arayüzü Yok)[/dim]",
        "Sadece Valorant'ı gizli modda başlatır ve korur. Tarayıcı/Web arayüzü açılmaz."
    )

    console.print(Align.center(Panel(menu_table, title="[bold white]BAŞLATMA MODU SEÇİMİ[/bold white]", border_style="red", expand=False)))
    
    choice = ""
    while choice not in ["1", "2", "3"]:
        try:
            choice = console.input("\n[bold yellow]Lütfen bir mod seçin [1 / 2 / 3] (Varsayılan 1): [/bold yellow]").strip()
            if not choice:
                choice = "1"
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Çıkış yapılıyor...[/yellow]")
            return

    if choice in ["2", "3"]:
        console.print("[bold red]⚡ KEPSLOCK Görünmez Mod aktif ediliyor...[/bold red]")
        if not start_stealth_engine():
            console.print("[yellow](!) Motor başlatılamadı, normal modda devam ediliyor.[/yellow]")
        else:
            console.print("[bold green]✔ Görünmez Mod devrede! Valorant KEPSLOCK motoruyla başlatıldı.[/bold green]")
            time.sleep(1.5)
    else:
        console.print("[bold green]✔ Normal mod ile başlatılıyor.[/bold green]")
        time.sleep(0.5)

    # 3. SEÇENEK: SADECE ÇEVRİMDIŞI MOD (Web arayüzü açılmaz)
    if choice == "3":
        if PYPRESENCE_AVAILABLE:
            def discord_offline_worker():
                global DISCORD_RPC
                try:
                    if not DISCORD_RPC:
                        DISCORD_RPC = Presence(DISCORD_CLIENT_ID)
                        DISCORD_RPC.connect()
                    DISCORD_RPC.update(
                        details="Valorant",
                        state="Görünmez Mod // Çevrimdışı",
                        start=RPC_START_TIME,
                        large_image="https://raw.githubusercontent.com/Keplorions/Valorant-InstaLocker/main/media/logo.png",
                        large_text="Valorant InstaLocker (Çevrimdışı)"
                    )
                except: pass
            threading.Thread(target=discord_offline_worker, daemon=True).start()

        os.system('cls' if os.name == 'nt' else 'clear')

        # ASCII Header (Centered)
        ascii_text = """[bold red]
  ██╗   ██╗ █████╗ ██╗      ██████╗     ██╗      ██████╗  ██████╗██╗  ██╗███████╗██████╗ 
  ██║   ██║██╔══██╗██║     ██╔═══██╗    ██║     ██╔═══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
  ██║   ██║███████║██║     ██║   ██║    ██║     ██║   ██║██║     █████╔╝ █████╗  ██████╔╝
  ╚██╗ ██╔╝██╔══██║██║     ██║   ██║    ██║     ██║   ██║██║     ██╔═██╗ ██╔══╝  ██╔══██╗
   ╚████╔╝ ██║  ██║███████╗╚██████╔╝    ███████╗╚██████╔╝╚██████╗██║  ██╗███████╗██║  ██║
[/bold red]"""
        console.print(Align.center(ascii_text))

        status_table = Table(box=box.ROUNDED, border_style="yellow", show_header=False, expand=True)
        status_table.add_column("Key", style="bold yellow", width=14)
        status_table.add_column("Val", style="bold white")
        status_table.add_row("DURUM", "[bold green]● GÖRÜNMEZ MOD AKTİF (KEPSLOCK)[/bold green]")
        status_table.add_row("WEB ARAYÜZÜ", "[dim]KAPALI (Sadece Çevrimdışı)[/dim]")
        status_table.add_row("BİLGİ", "Arkadaşlarınız sizi çevrimdışı görüyor. Oyunun tadını çıkarın!")
        status_table.add_row("ÇIKIŞ", "[bold yellow]Programı sonlandırmak için CTRL + C tuşlarına basın.[/bold yellow]")
        console.print(Align.center(Panel(status_table, title="[bold white]SADECE ÇEVRİMDIŞI MOD[/bold white]", border_style="bright_black", expand=False)))
        console.print(Align.center("[dim italic]Valorant koruma motoru aktif... İyi oyunlar![/dim italic]\n"))
        
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, EOFError):
            pass
        return

    # Ajan veritabanını güncelle
    if not fetch_agent_database():
        console.print("[yellow]Ajan veritabanı güncellenemedi, yerel liste kullanılacak.[/yellow]")

    # v29.0: Doğrudan Web Moduna geçiş
    run_web_mode()


if __name__ == "__main__":
    from rich.columns import Columns
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        try:
            stop_stealth_engine()
            if DISCORD_RPC:
                DISCORD_RPC.close()
            console.print("\n[bold yellow]👋 Program kapatıldı. İyi oyunlar![/bold yellow]")
        except:
            pass
        os._exit(0)
    except Exception as e:
        try:
            stop_stealth_engine()
            if DISCORD_RPC:
                DISCORD_RPC.close()
            console.print(f"\n[bold red](!) Beklenmedik bir hata oluştu: {e}[/bold red]")
        except:
            pass
