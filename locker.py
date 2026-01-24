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
from flask import Flask, render_template_string, jsonify, request
from ctypes import wintypes
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.live import Live
from rich.layout import Layout

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
                    SKIN_CACHE[uuid] = {"name": name, "icon": icon}
                    base_count += 1
                
                # Levels
                for item in skin.get("levels", []):
                    item_uuid = item.get("uuid")
                    if item_uuid:
                        item_icon = heal_url(item.get("displayIcon") or item.get("fullRender")) or icon
                        SKIN_CACHE[item_uuid] = {"name": name, "icon": item_icon}
                        level_count += 1
                
                # Chromas
                for item in skin.get("chromas", []):
                    item_uuid = item.get("uuid")
                    if item_uuid:
                        item_icon = heal_url(item.get("displayIcon") or item.get("fullRender")) or icon
                        SKIN_CACHE[item_uuid] = {"name": name, "icon": item_icon}
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
        .discriminator-v10 { font-size: 0.7em; color: #666; font-weight: 500; margin-left: 2px; }

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
            width: 20px; height: 20px; border-radius: 50%; 
            background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08);
            display: inline-flex; align-items: center; justify-content: center;
            cursor: pointer; transition: 0.3s; color: #fff; 
            font-weight: 900; font-size: 13px; margin-left: 8px; vertical-align: middle; 
            padding: 0; box-sizing: border-box; overflow: hidden;
            text-indent: 1px; /* Optical nudge for the ? character */
        }
        .info-btn:hover { background: rgba(255,255,255,0.15); border-color: rgba(255,255,255,0.2); box-shadow: 0 0 10px rgba(255,255,255,0.1); }

        /* Signature Animation (v44.61) */
        @keyframes signaturePulse {
            0%, 100% { text-shadow: 0 0 5px var(--accent-glow); opacity: 0.8; }
            50% { text-shadow: 0 0 20px var(--accent), 0 0 30px var(--accent-glow); opacity: 1; }
        }
        .signature-glow {
            animation: signaturePulse 3s ease-in-out infinite;
            cursor: default;
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
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
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
    <div class="container">
        <!-- Header -->
        <header class="glass-panel">
            <div style="display:flex; align-items:center;">
                <div>
                    <h1>VALO <span style="color:var(--accent)">LOCKER</span> <span class="version-badge">PREMIUM v44.90</span><div class="info-btn" onclick="toggleModal(true)">?</div></h1>
                    <div style="font-size:1em; color:#888; margin-top:5px; font-family:'Rajdhani', sans-serif; font-weight:600; letter-spacing:1px; display:flex; align-items:center; gap:12px;">
                        DARKSIDE ELITE GAMING DASHBOARD
                        <span style="width:4px; height:4px; background:rgba(255,255,255,0.1); border-radius:50%;"></span>
                        <span class="signature-glow" style="color:var(--accent); font-weight:800; letter-spacing:2px; font-size:0.9em;">BY'KEPLERB</span>
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
                    <div class="toggle-container" title="Otomatik hareket ederek AFK kalmanı engeller">
                        <label class="toggle-switch">
                            <input type="checkbox" id="afk-toggle" onchange="toggleAfk(this.checked)">
                            <span class="toggle-slider"></span>
                        </label>
                        <span style="font-size:0.7em; font-weight:800; color:#888;">ANTI-AFK</span>
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
                'map': 'HARİTA',
                'unknown': 'Bilinmiyor',
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
                'map': 'MAP',
                'unknown': 'Unknown',
                'phases': {
                    'WAITING': 'WAITING',
                    'PREGAME': 'CHARACTER SELECTION',
                    'INGAME': 'IN PROGRESS',
                    'MATCH_END': 'MATCH END'
                }
            }
        };

        let currentLang = localStorage.getItem('valolocker_lang') || 'en';

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
                $(this).text(t(key));
            });
            // Re-render components that use translations
            if (lastData) updateDataFromObj(lastData);
        }

        // Red Neon VFX Trail Logic (v44.75)
        const particles = [];
        const particleCount = 20;

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

        let mX = 0, mY = 0;
        document.addEventListener('mousemove', (e) => {
            mX = e.clientX;
            mY = e.clientY;
        });

        function animateVFX() {
            // Increased offset for deeper "behind" effect
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

        function toggleModal(show) {
            const modal = $('#info-modal');
            if(show) {
                modal.css('display', 'flex');
                setTimeout(() => modal.addClass('is-active'), 10);
            } else {
                modal.removeClass('is-active');
                setTimeout(() => modal.css('display', 'none'), 500);
            }
        }

        console.log("VALO LOCKER PREMIUM v44.0 INITIALIZED");
        let selectedAgent = null;
        let isAfkActive = false;

        function showNotification(msg, type = 'info') {
            const container = document.getElementById('notification-container');
            const notif = document.createElement('div');
            notif.className = `notification ${type}`;
            notif.innerHTML = `<span>${msg}</span>`;
            container.appendChild(notif);
            setTimeout(() => {
                notif.style.opacity = '0';
                setTimeout(() => notif.remove(), 500);
            }, 5000);
        }

        let AGENT_GROUPS = {};
        
        async function fetchAgents() {
            const res = await fetch('/api/agents');
            AGENT_GROUPS = await res.json();
            renderOriginalGrid();
        }

        function renderOriginalGrid() {
            const grid = $('#agent-grid');
            grid.empty();
            
            // Tüm ajanları tek bir listede topla ve alfabetik sırala
            let allAgents = [];
            Object.values(AGENT_GROUPS).forEach(group => {
                allAgents = allAgents.concat(group);
            });
            
            allAgents.sort((a,b) => a.name.localeCompare(b.name)).forEach(agent => {
                const btn = $(`
                    <div class="agent-btn ${selectedAgent === agent.name ? 'active' : ''}" onclick="selectAgent('${agent.name}', this)">
                        <img src="${agent.icon}" alt="${agent.name}">
                    </div>
                `);
                grid.append(btn);
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

        let lastData = null;

        function updateData() {
            $.get("/api/data", function(data) {
                lastData = data;
                updateDataFromObj(data);
            });
        }

        function updateDataFromObj(data) {
                const isConnected = data.status.includes("Bağlı");
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
                const COLORS = ['#ff4655', '#2ecc71', '#3498db', '#f1c40f', '#9b59b6', '#e67e22'];
                allPlayers.forEach(p => { if (p.party_id && pt[p.party_id] > 1 && !pm[p.party_id]) pm[p.party_id] = { i: pIdx++, c: COLORS[(pIdx-2)%COLORS.length] }; });

                if (data.allies) {
                    const me = data.allies.find(p => p.is_me);
                    const btn = document.getElementById('lock-btn');
                    if (me && me.locked && me.agent !== "Seçiyor...") {
                        btn.innerText = t('btn_locked');
                        btn.disabled = true;
                        btn.style.opacity = "0.5";
                        document.getElementById('lock-status').innerHTML = `<span style="color:var(--success); font-weight:900;">${me.agent.toUpperCase()} ${t('btn_locked')}!</span>`;
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
                let s = 0, g = new Set();
                players.forEach(p => { if (p.party_id && pm[p.party_id]) g.add(p.party_id); else s++; });
                $(summarySelector).text(`${g.size} GROUPS | ${s} SOLO`);
            }
            players.forEach(p => {
                const kpStyle = p.rank === "Radyant" || p.rank.includes("İmmo") ? "color:#ffb100" : "color:rgba(255,255,255,0.4)";
                const kpDisplay = (p.kp !== undefined && p.rank !== "Unranked") ? `<div class="rank-kp-v10" style="${kpStyle}">${p.kp} KP</div>` : '';
                const partyTag = (p.party_id && pm[p.party_id]) ? `<div class="party-tag" style="color:${pm[p.party_id].c}; border-color:${pm[p.party_id].c}">GRP ${pm[p.party_id].i}</div>` : '';
                
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
                
                const pNameBase = p.player_name || p.name || "Unknown";
                const pNameParts = pNameBase.split('#');
                const pNameDisplay = `<span class="player-name-v9 ${p.is_me ? 'is-me' : ''}">${pNameParts[0]}</span><span class="discriminator-v10">${pNameParts[1] ? '#' + pNameParts[1] : ''}</span>`;

                const row = `<div class="player-row ${teamType} ${p.is_me ? 'me' : ''}">
                    <div class="rank-card">
                        <img src="${p.rank_image}" class="rank-icon-v10">
                        <div class="rank-name-v10">${(p.rank_obj && p.rank_obj[currentLang]) ? p.rank_obj[currentLang] : (p.rank || "Unknown")}</div>
                        ${kpDisplay}
                    </div>
                    <div class="profile-card">
                        <div class="agent-box-v13 ${p.agent === "SELECTING" ? 'is-selecting' : ''}">
                            <img src="${agentSrc}" class="${agentClass}" onerror="this.src='https://media.valorant-api.com/agents/add6443a-4571-4c46-bd0a-ce87ee364b67/displayicon.png'; this.parentNode.classList.add('is-selecting');">
                            <div class="mystery-q">?</div>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px; margin-top:2px;">
                            <div class="agent-name-v10">${agentName}</div>
                            <div class="level-badge">${p.level || "0"}</div>
                        </div>
                    </div>
                    <div class="info-block">
                        <div>${pNameDisplay}</div>
                        <div style="margin-top:5px;">${partyTag}</div>
                    </div>
                    <div class="skin-deck">${skins}</div>
                </div>`;
                container.append(row);
            });
        }

        $(document).ready(() => {
            setLanguage(currentLang);
            fetchAgents();
            setInterval(updateData, 2000);
        });
    </script>
</body>
</html>
"""

# DOĞRU UUID'LER & Kategoriler (API'den dinamik dolacak)
AGENTS = {}
AGENT_DATA = {} # name -> {"role": str, "icon": str, "uuid": str}

def fetch_agent_database():
    """Valorant-api.com'dan en güncel ajan listesini ve rollerini çeker"""
    global AGENTS, AGENT_DATA
    try:
        with console.status("[bold cyan]Ajan veritabanı güncelleniyor...[/bold cyan]", spinner="dots"):
            response = requests.get("https://valorant-api.com/v1/agents", params={"language": "tr-TR", "isPlayableCharacter": "true"})
            if response.status_code == 200:
                data_api = response.json()["data"]
                
                if len(data_api) > 0:
                    AGENTS.clear()
                    AGENT_DATA.clear()

                for agent in data_api:
                    name = agent.get("displayName")
                    uuid = agent.get("uuid")
                    role = agent.get("role", {}).get("displayName", "Diğer")
                    icon = heal_url(agent.get("displayIcon"))
                    
                    if name and uuid:
                        AGENTS[name] = uuid
                        AGENT_DATA[name] = {
                            "uuid": uuid,
                            "role": role,
                            "icon": icon
                        }
                return True
    except:
        return False
    return False

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
    "/Game/Maps/Juliett/Sunset": "Sunset", # v27.4: Double T hybrid
    "/Game/Maps/Rook/Rook": "Corrode",
    "/Game/Maps/Infinity/Infinity": "Abyss", # v25.7: User debug confirmed Abyss
    "/Game/Maps/Extraction/Abyss": "Abyss",
    "/Game/Maps/Corrode/Corrode": "Abyss", # Keeping as fallback
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
    path = os.path.join(os.getenv('LOCALAPPDATA'), 'Riot Games', 'Riot Client', 'Config', 'lockfile')
    try:
        with open(path, 'r') as f:
            data = f.read().split(':')
            return {'port': data[2], 'password': data[3]}
    except:
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
        
        self.puuid = None
        self.access_token = None
        self.entitlements = None
        self.version = None
        self.shard = "eu" # Varsayılan EU (TR)
        self.region = "eu"
        self._name_cache = {} # Kalıcı isim önbelleği
        self._rank_cache = {} # Kalıcı rütbe önbelleği
        self._tier_cache = {} # Kalıcı tier id önbelleği
        self._kp_cache = {}   # v38.0: Kalıcı KP önbelleği
        
    def get_player_rank(self, puuid):
        """Oyuncunun Competitive Rank bilgisini ve Tier ID'sini al"""
        try:
            # Önce cache kontrolü
            if puuid in self._rank_cache and puuid in self._tier_cache:
                return self._rank_cache[puuid]

            url = f"https://pd.{self.shard}.a.pvp.net/mmr/v1/players/{puuid}"
            headers = self.get_headers()
            r = self.session.get(url, headers=headers, verify=False)
            
            if r.status_code == 200:
                data = r.json()
                # En son oynanan sezon veya güncel veriler
                queue_skills = data.get("QueueSkills", {}).get("competitive", {})
                tier = queue_skills.get("TierAfterUpdate", 0) # Eğer maç oynamamışsa 0 dönebilir
                
                # Seasonal Info
                # Bazen QueueSkills boştur, LatestCompetitiveUpdate'e bakmak gerekir
                if tier == 0:
                     # Basitçe 0 diyelim
                     pass

                # Cache updates
                self._tier_cache[puuid] = tier
                
                # Rank Name
                # RANK_NAMES global dictionary is needed in locker.py context, assume it exists or use fallback
                # But actually we have a RANK_NAMES map likely defined somewhere? 
                # If not, let's assume we return a string based on Tier ID logic or just unknown
                # Checking code: line 803 uses RANK_NAMES.
                try:
                    rank_name = RANK_NAMES.get(tier, "Unranked")
                except:
                    rank_name = f"Tier {tier}"
                    
                self._rank_cache[puuid] = rank_name
                return rank_name
        except:
            pass
        return "Bilinmiyor"

    def connect(self):
        try:
            r = self.session.get(f"{self.base_url}/entitlements/v1/token", headers=self.headers)
            if r.status_code == 200:
                data = r.json()
                self.puuid = data.get('subject')
                self.access_token = data.get('accessToken')
                self.entitlements = data.get('token')
                
                r2 = self.session.get(f"{self.base_url}/product-session/v1/external-sessions", headers=self.headers)
                if r2.status_code == 200:
                    for sid, sdata in r2.json().items():
                        if sdata.get("productId") == "valorant":
                            # Doğru versiyon string'ini (release-xx.xx...) bulmaya çalış
                            try:
                                # 2. Yol: ShooterGame.log dosyasından versiyonu çek (En Garantisi)
                                local_appdata = os.getenv('LOCALAPPDATA')
                                log_path = os.path.join(local_appdata, "VALORANT", "Saved", "Logs", "ShooterGame.log")
                                
                                if os.path.exists(log_path):
                                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                                        for line in f:
                                            if "CI server version:" in line:
                                                # Örnek: ... CI server version: release-12.00-30-4183428
                                                parts = line.split("CI server version:")
                                                if len(parts) > 1:
                                                    self.version = parts[1].strip()
                                                    # Version formatı düzeltme: release-12.00-30-4183428 -> release-12.00-shipping-30-4183428
                                                    if "-shipping-" not in self.version and len(self.version.split("-")) == 4:
                                                        v_parts = self.version.split("-")
                                                        self.version = f"{v_parts[0]}-{v_parts[1]}-shipping-{v_parts[2]}-{v_parts[3]}"
                                                    break
                                else:
                                    # Log dosyası yoksa hash kullan (çalışmaz ama fallback)
                                    self.version = sdata.get("version")
                            except:
                                self.version = sdata.get("version")

                            # Shard ve Region tespiti
                            launch_args = sdata.get("launchConfiguration", {}).get("arguments", [])
                            for arg in launch_args:
                                if arg.startswith("-pp="):
                                    self.region = arg.split("=")[1]
                                if arg.startswith("-shard="):
                                    self.shard = arg.split("=")[1]
                            
                            break
                return True
        except:
            pass
        return False
    
    def get_headers(self):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Riot-Entitlements-JWT": self.entitlements,
            "Content-Type": "application/json",
            "User-Agent": "RiotClient/43.0.1.4393933.4384232 rso-auth (Windows;10;;Professional, x64)"
        }
        if self.version:
            headers["X-Riot-ClientVersion"] = self.version
            headers["X-Riot-ClientPlatform"] = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"
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
        """Toplu şekilde oyuncu isimlerini al - Çok daha hızlıdır"""
        results = {}
        to_fetch = []
        
        for puuid in puuids:
            if puuid in self._name_cache:
                results[puuid] = self._name_cache[puuid]
            else:
                to_fetch.append(puuid)
        
        if not to_fetch:
            return results

        try:
            url = f"https://pd.{self.shard}.a.pvp.net/name-service/v2/players"
            r = self.session.put(url, headers=self.get_headers(), json=to_fetch, verify=False)
            if r.status_code == 200:
                data = r.json()
                for player in data:
                    name = f"{player.get('GameName', '?')}#{player.get('TagLine', '?')}"
                    puuid = player.get('Subject')
                    self._name_cache[puuid] = name
                    results[puuid] = name
        except:
            pass
            
        # Eksik kalanları doldur
        for puuid in to_fetch:
            if puuid not in results:
                results[puuid] = "Bilinmiyor"
        
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
        """Oyuncunun rütbe (MMR) ve KP bilgisini al"""
        try:
            url = f"https://pd.{self.shard}.a.pvp.net/mmr/v1/players/{puuid}"
            headers = self.get_headers()
            r = self.session.get(url, headers=headers, verify=False)
            
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
                if tier == 0:
                    try:
                        seasonal = data.get("QueueSkills", {}).get("competitive", {}).get("SeasonalInfoBySeasonID", {})
                        if seasonal:
                            for s_id, s_info in seasonal.items():
                                s_tier = s_info.get("CompetitiveTier", 0)
                                if s_tier > tier: 
                                    tier = s_tier
                                    kp = s_info.get("RankedRating", 0)
                    except: pass
                
                self._tier_cache[puuid] = tier
                self._kp_cache[puuid] = kp
                
                return RANK_NAMES.get(tier, "Unranked")
        except:
            pass
        return "[dim]Bilinmiyor[/dim]"



        
    def get_parties_from_presence(self):
        """Yerel Riot Client üzerinden party ve rank bilgilerini çek"""
        try:
            auth = base64.b64encode(f"riot:{self.password}".encode()).decode()
            local_headers = {"Authorization": f"Basic {auth}"}
            
            # /chat/v4/presences bazen kısıtlıdır, alternatifleri de tarayalım
            r = self.session.get(f"{self.base_url}/chat/v4/presences", headers=local_headers, verify=False)
            if r.status_code == 200:
                presences = r.json().get("presences", [])
                
                presence_map = {}
                for p in presences:
                    puuid = p.get("puuid")
                    private_b64 = p.get("private")
                    if puuid and private_b64:
                        try:
                            # Base64 decode ve JSON parse
                            decoded = json.loads(base64.b64decode(private_b64).decode())
                            
                            # Rütbe tespiti (Çoklu anahtar kontrolü)
                            rank = decoded.get("competitiveTier", 0)
                            if rank == 0: rank = decoded.get("rankedTier", 0)
                            if rank == 0: rank = decoded.get("rank", 0)
                            
                            # PARTY ID TESPİTİ (En kritik kısım)
                            # Riot farklı sürümlerde farklı anahtarlar kullanabiliyor
                            party_id = decoded.get("partyId")
                            if not party_id: party_id = decoded.get("partyID")
                            if not party_id: party_id = decoded.get("party_id")
                            if not party_id: party_id = decoded.get("l_partyId") # Bazı leaklerde görülen format
                            
                            # Fallback: matchPresenceData içinden ayıkla
                            if not party_id and "matchPresenceData" in decoded:
                                party_id = decoded["matchPresenceData"].get("partyId")

                            presence_map[puuid] = {
                                "rank": rank,
                                "level": decoded.get("accountLevel", 0),
                                "party_id": party_id
                            }
                        except: continue
                # 2. Alternatif: /presence/v1/presences (Bazen daha kapsayıcıdır)
            r2 = self.session.get(f"{self.base_url}/presence/v1/presences", headers=local_headers, verify=False)
            if r2.status_code == 200:
                p2 = r2.json().get("presences", [])
                # Mevcut map'e ekle veya güncelle
                for p in p2:
                    puuid = p.get("puuid")
                    private_b64 = p.get("private")
                    if puuid and private_b64 and puuid not in presence_map:
                        try:
                            decoded = json.loads(base64.b64decode(private_b64).decode())
                            rank = decoded.get("competitiveTier", decoded.get("rankedTier", 0))
                            party_id = decoded.get("partyId") or decoded.get("partyID") or decoded.get("party_id")
                            if not party_id and "matchPresenceData" in decoded:
                                party_id = decoded["matchPresenceData"].get("partyId")
                            
                            presence_map[puuid] = {
                                "rank": rank,
                                "level": decoded.get("accountLevel", 0),
                                "party_id": party_id
                            }
                        except: continue

            return presence_map
        except:
            return {}

    def get_all_players(self, match_id, match_type="pregame"):
        """Maçtaki tüm oyuncuları al (pregame veya coregame)"""
        if match_type == "pregame":
            details = self.get_match_details(match_id)
            ally_key = "AllyTeam"
            enemy_key = "EnemyTeam"
            players_key = "Players"
        else:
            details = self.get_coregame_details(match_id)
            ally_key = "Players"  # Coregame farklı format kullanıyor
            enemy_key = None
            players_key = None
        
        if not details:
            return None, None, None
        
        ally_players = []
        enemy_players = []
        party_colors = {}
        party_counts = {} # v24.1: Crucial fix for NameError
        color_index = 0
        # CMD uyumlu renkli etiketler - numaralı party gösterimi
        colors = [
            "[bold red]P1[/bold red]",
            "[bold green]P2[/bold green]", 
            "[bold blue]P3[/bold blue]",
            "[bold yellow]P4[/bold yellow]",
            "[bold magenta]P5[/bold magenta]",
            "[bold cyan]P6[/bold cyan]"
        ]
        
        presence_data = self.get_parties_from_presence()
        
        target_players = []
        if match_type == "pregame":
            ally_team = details.get(ally_key, {})
            for p in ally_team.get(players_key, []): target_players.append(p)
            if enemy_key:
                enemy_team = details.get(enemy_key, {})
                if enemy_team:
                    for p in enemy_team.get(players_key, []): target_players.append(p)
        else:
            target_players = details.get("Players", [])

        # DEBUG: Chat Conversations (Party Chat Bulma)
        try:
            r = self.session.get(f"{self.base_url}/chat/v6/conversations", headers=self.headers, verify=False)
            if r.status_code == 200:
                convs = r.json().get("conversations", [])
                for c in convs:
                    ctype = c.get("type")
                    cmembers = [m.get("puuid") for m in c.get("members", [])]
                    
                    if (ctype == "group" or ctype == "party") and len(cmembers) > 1:
                            found_pid = c.get("id")
                            for m_puuid in cmembers:
                                if m_puuid not in presence_data: presence_data[m_puuid] = {"party_id": found_pid, "rank": 0}
                                else: presence_data[m_puuid]["party_id"] = found_pid
        except: pass

        for p in target_players:
            puuid = p.get("Subject", "")
            pid = p.get("PartyID", "")
            if (not pid or pid == "00000000-0000-0000-0000-000000000000") and puuid in presence_data:
                pid = presence_data[puuid].get("party_id")
            
            if pid and pid != "00000000-0000-0000-0000-000000000000":
                party_counts[pid] = party_counts.get(pid, 0) + 1

        # 2. Aşama: İsimleri toplu çek
        puuids = [p.get("Subject") for p in target_players if p.get("Subject")]
        names_map = self.get_player_names(puuids)

        def process_player(player):
            nonlocal color_index
            puuid = player.get("Subject", "")
            name = names_map.get(puuid, "Bilinmiyor")
            
            # 1. Öncelik: Presence verisi
            p_info = presence_data.get(puuid, {})
            party_id = p_info.get("party_id", player.get("PartyID", ""))
            presence_rank_tier = p_info.get("rank", 0)
            presence_kp = p_info.get("kp", 0)
            
            # Rank ve KP bilgisi (Self caching)
            kp = 0
            if puuid in self._rank_cache:
                rank = self._rank_cache[puuid]
                presence_rank_tier = self._tier_cache.get(puuid, 0)
                kp = self._kp_cache.get(puuid, 0)
            elif presence_rank_tier > 0:
                rank = RANK_NAMES.get(presence_rank_tier, "Unranked")
                kp = presence_kp
                self._rank_cache[puuid] = rank
                self._tier_cache[puuid] = presence_rank_tier
                self._kp_cache[puuid] = kp
            else:
                rank = self.get_player_rank(puuid)
                if rank == "[dim]Bilinmiyor[/dim]" and presence_rank_tier is not None:
                    rank = RANK_NAMES.get(presence_rank_tier, "Unranked")
                self._rank_cache[puuid] = rank
                presence_rank_tier = self._tier_cache.get(puuid, 0)
                kp = self._kp_cache.get(puuid, 0)
            
            # Seviye bilgisi
            agent_uuid = player.get("CharacterID", "")
            agent_name = self.uuid_to_agent_name(agent_uuid)
            is_me = puuid == self.puuid
            team_id = player.get("TeamID", "")
            
            is_locked = player.get("CharacterSelectionState", "") == "locked"
            if match_type == "coregame":
                is_locked = True

            level = player.get("PlayerIdentity", {}).get("AccountLevel", 0)
            if not level or level == 0:
                level = player.get("AccountLevel", 0)
            
            # 3. Yol: Presence Fallback
            if (not level or level == 0) and p_info.get("level", 0) > 0:
                level = p_info.get("level")

            # 4. Yol: Match History Bypass (Gizli levelleri aşmak için)
            if not level or level == 0:
                cache_key = f"lvl_{puuid}"
                if hasattr(self, "_level_cache") and cache_key in self._level_cache:
                    level = self._level_cache[cache_key]
                else:
                    try:
                        # Çok hızlı bir kontrol: Maç geçmişine bak
                        url = f"https://pd.{self.shard}.a.pvp.net/match-history/v1/history/{puuid}?startIndex=0&endIndex=1"
                        r = self.session.get(url, headers=self.get_headers(), verify=False)
                        if r.status_code == 200:
                            history = r.json().get("History", [])
                            if history:
                                match_id = history[0].get("MatchID")
                                # Maç detaylarında seviye gizlenmez (Platform sızıntısı)
                                details_url = f"https://pd.{self.shard}.a.pvp.net/match-details/v1/matches/{match_id}"
                                r2 = self.session.get(details_url, headers=self.get_headers(), verify=False)
                                if r2.status_code == 200:
                                    m_data = r2.json()
                                    for m_player in m_data.get("players", []):
                                        if m_player.get("subject") == puuid:
                                            level = m_player.get("accountLevel", 0)
                                            if level > 0:
                                                if not hasattr(self, "_level_cache"): self._level_cache = {}
                                                self._level_cache[cache_key] = level
                                            break
                    except: pass

            return {
                "puuid": puuid,
                "name": name,
                "agent": agent_name,
                "agent_uuid": agent_uuid,
                "locked": is_locked,
                "level": str(level) if level else "0",
                "rank": rank,
                "kp": kp,
                "tier": presence_rank_tier, # Added Tier ID for image lookup
                "is_me": is_me,
                "team_id": team_id,
                "party_id": party_id
            }
        
        if match_type == "pregame":
            # Pregame format
            ally_team = details.get(ally_key, {})
            for player in ally_team.get(players_key, []):
                ally_players.append(process_player(player))
            
            if enemy_key:
                enemy_team = details.get(enemy_key, {})
                if enemy_team:
                    for player in enemy_team.get(players_key, []):
                        enemy_players.append(process_player(player))
        else:
            # Coregame format - tüm oyuncular tek listede
            all_players = details.get("Players", [])
            my_team = None
            
            # Önce kendi takımımızı bul
            for player in all_players:
                if player.get("Subject") == self.puuid:
                    my_team = player.get("TeamID")
                    break
            
            for player in all_players:
                p_data = process_player(player)
                if player.get("TeamID") == my_team:
                    ally_players.append(p_data)
                else:
                    enemy_players.append(p_data)
        
        map_id = details.get("MapID", "Bilinmiyor")
        map_name = VAL_MAPS.get(map_id, map_id.split('/')[-1] if '/' in map_id else "Bilinmiyor")
        
        return ally_players, enemy_players, {}, map_name
    
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
            idx = list(AGENTS.keys()).index(agent) + 1
            t.add_row(f"[{color}]{idx:2}[/]", f"[white]{agent}[/]")
        return t

    grid = Table.grid(expand=True)
    grid.add_column(ratio=1); grid.add_column(ratio=1); grid.add_column(ratio=1); grid.add_column(ratio=1)
    grid.add_row(
        Panel(get_role_table(DUELISTS, "red"), title="[bold red]DÜELLOCU[/]", border_style="dim", box=box.SQUARE),
        Panel(get_role_table(SENTINELS, "green"), title="[bold green]GÖZCÜ[/]", border_style="dim", box=box.SQUARE),
        Panel(get_role_table(INITIATORS, "blue"), title="[bold blue]ÖNCÜ[/]", border_style="dim", box=box.SQUARE),
        Panel(get_role_table(CONTROLLERS, "magenta"), title="[bold magenta]KONTROL[/]", border_style="dim", box=box.SQUARE)
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
                ally_table.add_column("LVL", justify="center", width=5)
                ally_table.add_column("RANK", justify="center", min_width=12)
                ally_table.add_column("Oyuncu", justify="left", min_width=20)
                ally_table.add_column("Ajan", justify="center", min_width=10)
                ally_table.add_column("Durum", justify="center", width=8)
                
                for p in players:
                    name_style = "[bold yellow]" if p["is_me"] else "[white]"
                    agent_disp = p["agent"] if p["agent"] != "Seçiyor..." else "[dim]Seçiyor...[/dim]"
                    if p["locked"] and agent_disp == "[dim]Seçiyor...[/dim]": agent_disp = "[dim italic]Ajan Gizli[/dim italic]"
                    status = "[green]OK[/green]" if p["locked"] else "[yellow]...[/yellow]"
                    ally_table.add_row(p["level"], p["rank"], f"{name_style}{p['name']}[/]", agent_disp, status)
                console.print(ally_table)
                
                # Enemy Table
                if enemies or game_started:
                    console.print()
                    enemy_table = Table(title="[bold red]KARŞI TAKIM[/bold red]", box=box.SQUARE, border_style="red")
                    enemy_table.add_column("LVL", justify="center", width=5)
                    enemy_table.add_column("RANK", justify="center", min_width=12)
                    enemy_table.add_column("Oyuncu", justify="left", min_width=20)
                    enemy_table.add_column("Ajan", justify="center", min_width=10)
                    enemy_table.add_column("Durum", justify="center", width=8)
                    
                    for p in (enemies or []):
                        agent_disp = p["agent"] if p["agent"] != "Seçiyor..." else "[dim]Seçiyor...[/dim]"
                        if (p["locked"] or game_started) and agent_disp == "[dim]Seçiyor...[/dim]": agent_disp = "[dim italic]Ajan Gizli[/dim italic]"
                        status = "[green]OK[/green]" if (p["locked"] or game_started) else "[yellow]...[/yellow]"
                        enemy_table.add_row(p["level"], p["rank"], f"[white]{p['name']}[/]", agent_disp, status)
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
                                        skin_name = SKIN_CACHE.get(socket_id, "Standart")
                                except:
                                    pass
                                
                                # İsim kısaltma
                                skin_name = skin_name.replace(" Standart", "")
                                
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

                # v37.5: Prefix-based robust matching
                target_weapons = {
                    "9c82e19d": "Vandal",
                    "ee8e8d15": "Phantom",
                    "1baa85b4": "Ghost",
                    "a03b24d3": "Operator",
                    "e336c6b8": "Sheriff"
                }

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
                            a_obj = {"tr": a_name, "en": a_name} # Agents names are universal mostly
                        
                        p_data = {
                            "rank": player.get("rank"),
                            "rank_obj": {"tr": RANK_NAMES.get(tier_id, "Bilinmiyor"), "en": RANK_NAMES_EN.get(tier_id, "Unknown")},
                            "kp": player.get("kp", 0),
                            "name": player.get("name"), 
                            "agent_obj": a_obj,
                            "agent": a_name,
                            "agent_uuid": player.get("agent_uuid"), "level": player.get("level"),
                            "agent_image": AGENT_ASSETS.get(a_name, ""),
                            "rank_image": RANK_ASSETS.get(tier_id, ""),
                            "is_me": player.get("is_me"), "locked": player.get("locked"),
                            "party_id": player.get("party_id"),
                            "vandal": "-", "vandal_img": "", "phantom": "-", "phantom_img": "",
                            "ghost": "-", "ghost_img": "", "op": "-", "op_img": "", "sheriff": "-", "sheriff_img": ""
                        }

                        # Loadout Logic
                        puuid_lower = (player.get("puuid") or "").lower()
                        loadout = next((v for k, v in match_loadouts.items() if k and k.lower() == puuid_lower), None)
                        if not loadout and player.get("agent") in AGENTS:
                            a_uuid = AGENTS[player["agent"]].lower()
                            loadout = next((v for k, v in match_loadouts.items() if k and k.lower() == a_uuid), None)

                        if loadout:
                            items = loadout.get("Guns") or loadout.get("Items") or {}
                            if isinstance(items, list): items = {g.get("ID"): g for g in items}
                            
                            for gun_id, g_data in items.items():
                                gid_l = str(gun_id).lower()
                                w_type = next((name for prefix, name in target_weapons.items() if gid_l.startswith(prefix)), None)
                                if w_type:
                                    # Dynamic Weapon Asset Sync (v44.8)
                                    default_icon = WEAPON_ASSETS.get(gid_l[:8], "")
                                    f_skin = {"tr": "Standart", "en": "Standard", "icon": default_icon}
                                    is_prem = False
                                    
                                    # Check sockets
                                    for s_val in g_data.get("Sockets", {}).values():
                                        sid = s_val.get("Item", {}).get("ID", "").lower()
                                        if sid in SKIN_CACHE:
                                            sc = SKIN_CACHE[sid]
                                            f_skin = {"tr": sc["tr"], "en": sc["en"], "icon": sc["icon"]}
                                            if sid != gid_l: is_prem = True; break
                                    
                                    # Fallback to SkinID
                                    if not is_prem and "SkinID" in g_data:
                                        sid = g_data["SkinID"].lower()
                                        if sid in SKIN_CACHE:
                                            sc = SKIN_CACHE[sid]
                                            f_skin = {"tr": sc["tr"], "en": sc["en"], "icon": sc["icon"]}

                                    # Final Sync & Override (v44.15)
                                    # v44.9: Clean level indicators from skin names
                                    import re
                                    def clean_skin_name(name):
                                        if not name: return name
                                        # Precisely remove level/rank indicators without nuking the name
                                        patterns = [
                                            r'\s*\(?(\d+\.\s*)?([Ss]eviye|[Ll]evel|[Aa]şama)\s*\d*\)?',
                                            r'\s*\(?[Ss]eviye\s*\d+\)?',
                                            r'\s*\(?[Ll]evel\s*\d+\)?',
                                            r'\s*\(?[Aa]şama\s*\d+\)?'
                                        ]
                                        for p in patterns:
                                            name = re.sub(p, '', name)
                                        return name.strip()
                                    
                                    f_skin["tr"] = clean_skin_name(f_skin.get("tr", ""))
                                    f_skin["en"] = clean_skin_name(f_skin.get("en", ""))
                                    
                                    # Robust Icon & Name Override for Standard Skins
                                    en_upper = f_skin.get("en", "").upper()
                                    is_standard = any(kw in en_upper for kw in ["STANDARD", "STANDART"]) or en_upper == w_type.upper()
                                    
                                    if not f_skin.get("icon") or is_standard:
                                        f_skin["icon"] = f_skin.get("icon") or default_icon
                                        if is_standard:
                                            f_skin["tr"] = "Standart"
                                            f_skin["en"] = "Standard"
                                            f_skin["icon"] = default_icon or f_skin["icon"]
                                    
                                    key = {"Vandal": "vandal", "Phantom": "phantom", "Ghost": "ghost", "Operator": "op", "Sheriff": "sheriff"}.get(w_type)
                                    if key:
                                        p_data[key+"_obj"] = f_skin
                                        p_data[key+"_img"] = heal_url(f_skin["icon"])
                                        # p_data[key] is handled by frontend via _obj

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
    # Gruba göre paketle
    grouped = {}
    for name, info in AGENT_DATA.items():
        role = info["role"]
        if role not in grouped: grouped[role] = []
        grouped[role].append({"name": name, "icon": info["icon"]})
    
    # Rolleri sıralı döndür (Opsiyonel)
    return jsonify(grouped)

@app.route('/api/lock/<agent_name>')
def lock_agent(agent_name):
    global web_locker
    if not web_locker: return jsonify({"status": "error", "msg": "Not connected"})
    
    def locker_thread():
        # Basit bir loop ile maç gelene kadar bekle
        console.print(f"[bold green]WEB: {agent_name} için otomatik kilit döngüsü başlatıldı...[/]")
        while True:
            try:
                pregame = web_locker.get_pregame()
                if pregame:
                    if agent_name in AGENTS:
                         # Ajanı seç ve kilitle
                         web_locker.lock_agent(pregame, AGENTS[agent_name])
                         console.print(f"[bold green]WEB: {agent_name} KİLİTLENDİ![/]")
                         break # Görev tamamlandı, döngüden çık
                time.sleep(0.5)
            except: 
                time.sleep(1)
    
    # Mevcut thread varsa durdurulmalı mı? Şimdilik basitçe yenisini başlatıyoruz.
    threading.Thread(target=locker_thread, daemon=True).start()
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
        # Fetch TR
        r_tr = requests.get("https://valorant-api.com/v1/weapons/skins", params={"language": "tr-TR"}, timeout=20)
        # Fetch EN
        r_en = requests.get("https://valorant-api.com/v1/weapons/skins", params={"language": "en-US"}, timeout=20)
        
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
    
    # AGENT ASSETS
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

    # Simple Pro Table
    status_table = Table.grid(expand=False, padding=(0, 2))
    status_table.add_column(style="dim cyan")
    status_table.add_column(style="bold white")
    
    status_table.add_row("DURUM", "[green]AKTİF[/green]")
    status_table.add_row("ADRES", "[underline]http://127.0.0.1:5000[/underline]")
    status_table.add_row("VERİ", f"{len(SKIN_CACHE)} Skin | {len(AGENT_ASSETS)} Ajan")
    status_table.add_row("SÜRÜM", "PRO v44.90 Stable")
    
    console.print(Align.center(Panel(status_table, title="[bold white]SİSTEM BİLGİSİ[/bold white]", border_style="bright_black", expand=False)))
    console.print(Align.center("[dim italic]Tarayıcı otomatik açılıyor, Valorant bekleniyor...[/dim italic]\n"))

    def valo_checker():
        global web_locker
        while True:
            try:
                if not web_locker:
                    lockfile = get_lockfile()
                    if lockfile:
                        temp_locker = Locker(lockfile)
                        if temp_locker.connect():
                            web_locker = temp_locker
            except: 
                web_locker = None
            time.sleep(5)
            
    threading.Thread(target=valo_checker, daemon=True).start()
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def main():
    os.system('chcp 65001 > nul')

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
            console.print("\n[bold yellow]👋 Program kapatıldı. İyi oyunlar![/bold yellow]")
        except:
            pass
        os._exit(0)
    except Exception as e:
        try:
            console.print(f"\n[bold red](!) Beklenmedik bir hata oluştu: {e}[/bold red]")
            input("\nKapatmak için ENTER'a basın...")
        except:
            pass
