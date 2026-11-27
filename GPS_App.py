import asyncio
import ctypes
import importlib
import inspect
import io
import json
import math
import os
import pkgutil
import re
import sys
import threading
import time
import webbrowser

class DummyStream(io.TextIOBase):
    def write(self, s):
        return len(s)
    def flush(self):
        pass
    def isatty(self):
        return False

if sys.stdout is None:
    sys.stdout = DummyStream()
if sys.stderr is None:
    sys.stderr = DummyStream()

import requests
import webview
from flask import Flask, jsonify, render_template_string, request
import pymobiledevice3.services as pmd3_services
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAVORITES_FILE = os.path.join(BASE_DIR, "favoritos.json")

def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []

def save_favorites(items):
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

HTML_PAGE = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="color-scheme" content="light dark" />
  <title>Simulador GPS</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    :root {
      --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif;
      --blue: #007aff; --green: #34c759; --red: #ff3b30; --orange: #ff9500;
      --green-t: #248a3d; --orange-t: #b25f00;
      --label: rgba(0,0,0,.88); --label2: rgba(60,60,67,.62); --sep: rgba(60,60,67,.18);
      --g-panel: rgba(255,255,255,.40); --g-card: rgba(255,255,255,.36); --g-ctrl: rgba(255,255,255,.58);
      --well: rgba(120,120,128,.16); --thumb: rgba(255,255,255,.94);
      --g-blur: 26px; --g-sat: 180%;
      --r-panel: 32px; --r-card: 24px; --r-ctrl: 16px;
      --spring: cubic-bezier(.34,1.56,.64,1); --ease: cubic-bezier(.25,.1,.25,1);
      --shadow: 0 8px 32px rgba(0,0,0,.14), 0 2px 6px rgba(0,0,0,.06);
      --hl: inset 0 1px 0 rgba(255,255,255,.6), inset 0 -1px 0 rgba(255,255,255,.1), inset 0 0 12px rgba(255,255,255,.08);
      --pop: rgba(255,255,255,.94);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0; height: 100vh; width: 100vw; overflow: hidden;
      font: 400 15px/1.3 var(--font); color: var(--label);
      background: #e5e5ea; user-select: none; -webkit-font-smoothing: antialiased;
      font-variant-numeric: tabular-nums;
    }
    input, select { user-select: text; }
    #map-wrap { position: fixed; inset: 0; }
    #map { width: 100%; height: 100%; }

    /* ---------- Liquid Glass ---------- */
    #sidebar-shell {
      position: fixed; top: 14px; left: 14px; width: 332px; max-height: calc(100vh - 28px);
      z-index: 1000; border-radius: var(--r-panel); background: var(--g-panel);
      -webkit-backdrop-filter: blur(var(--g-blur)) saturate(var(--g-sat)) brightness(1.05);
      backdrop-filter: blur(var(--g-blur)) saturate(var(--g-sat)) brightness(1.05);
      box-shadow: var(--shadow), var(--hl);
      display: flex; flex-direction: column; overflow: hidden;
      transition: transform .5s var(--spring), opacity .25s var(--ease);
    }
    #sidebar-shell.refract {
      backdrop-filter: url(#liquid) blur(var(--g-blur)) saturate(var(--g-sat)) brightness(1.05);
    }
    #sidebar-shell.collapsed { transform: translateX(calc(-100% - 28px)); opacity: 0; pointer-events: none; }
    #sidebar-shell::after {
      content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
      background: radial-gradient(280px circle at var(--mx, 30%) var(--my, 0%), rgba(255,255,255,.28), transparent 62%);
      mix-blend-mode: soft-light;
    }
    /* borde especular */
    #sidebar-shell::before, #btn-toggle-bar::before, .card::before, .section::before,
    .search-wrap::before, .btn:not(.btn-plain)::before, .leaflet-bar::before {
      content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1px; pointer-events: none; z-index: 3;
      background: linear-gradient(135deg, rgba(255,255,255,.85), rgba(255,255,255,0) 38%, rgba(255,255,255,0) 62%, rgba(255,255,255,.45));
      -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
      -webkit-mask-composite: xor; mask-composite: exclude;
    }
    #sidebar-scroll {
      overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px;
      scrollbar-width: none; position: relative; z-index: 1;
    }
    #sidebar-scroll::-webkit-scrollbar { display: none; }

    .header { display: flex; align-items: center; justify-content: space-between; min-height: 34px; padding: 0 2px; }
    .app-title { font-size: 20px; font-weight: 700; letter-spacing: -.02em; }

    .card, .section { position: relative; border-radius: var(--r-card); background: var(--g-card); box-shadow: var(--hl); }
    .card { padding: 14px; display: flex; flex-direction: column; gap: 12px; }
    .card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .card-title { font-size: 15px; font-weight: 600; }

    /* ---------- Botones ---------- */
    .btn {
      position: relative; height: 40px; padding: 0 16px; border: 0; border-radius: 999px;
      font: 600 15px/1 var(--font); color: var(--blue); background: var(--g-ctrl);
      box-shadow: var(--hl), 0 1px 3px rgba(0,0,0,.06); cursor: pointer; white-space: nowrap;
      transition: transform .35s var(--spring), background .2s var(--ease), filter .2s var(--ease);
    }
    .btn:active { transform: scale(.96); filter: brightness(1.07); }
    .btn-primary { color: #fff; background: linear-gradient(180deg, #3d9bff, var(--blue)); box-shadow: inset 0 1px 0 rgba(255,255,255,.35), 0 4px 14px rgba(0,122,255,.32); }
    .btn-stop { color: var(--red); background: rgba(255,59,48,.14); }
    .btn-plain { background: transparent; box-shadow: none; padding: 0 10px; height: 32px; font-weight: 500; }
    .btn:focus-visible, .seg-opt:focus-visible, .search-go:focus-visible { outline: 3px solid rgba(0,122,255,.45); outline-offset: 2px; }
    @media (hover: hover) { .btn:hover { filter: brightness(1.05); } .btn-plain:hover { background: var(--well); } }

    .row { display: flex; gap: 8px; align-items: center; }
    .row > * { min-width: 0; }
    .grow { flex: 1; }

    /* ---------- Búsqueda ---------- */
    .search-wrap {
      position: relative; display: flex; align-items: center; gap: 8px; height: 46px; padding: 0 7px 0 15px;
      border-radius: 999px; background: var(--g-ctrl); box-shadow: var(--hl); color: var(--label2);
      transition: box-shadow .2s var(--ease);
    }
    .search-wrap:focus-within { box-shadow: var(--hl), 0 0 0 3px rgba(0,122,255,.3); }
    .search-wrap input { flex: 1; min-width: 0; border: 0; background: transparent; outline: 0; font: 400 15px var(--font); color: var(--label); }
    input::placeholder { color: var(--label2); }
    .search-go {
      flex: none; width: 32px; height: 32px; border: 0; border-radius: 50%; display: grid; place-items: center;
      color: #fff; background: var(--blue); cursor: pointer; transition: transform .35s var(--spring);
    }
    .search-go:active { transform: scale(.92); }
    #suggest-list {
      position: absolute; top: 54px; left: 0; right: 0; max-height: 200px; overflow-y: auto; display: none; z-index: 2000;
      background: var(--pop); border-radius: 20px; box-shadow: var(--shadow); color: var(--label); scrollbar-width: none;
    }
    .suggest-item { padding: 10px 14px; font-size: 13px; cursor: pointer; line-height: 1.35; border-bottom: .5px solid var(--sep); }
    .suggest-item:last-child { border-bottom: 0; }
    @media (hover: hover) { .suggest-item:hover { background: rgba(0,122,255,.12); } }

    /* ---------- Estado ---------- */
    .status-line { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
    .status-pill {
      --c: var(--orange); --t: var(--orange-t);
      display: inline-flex; align-items: center; gap: 7px; padding: 5px 12px 5px 10px; border-radius: 999px;
      font-size: 13px; font-weight: 600; color: var(--t);
      background: color-mix(in srgb, var(--c) 16%, transparent);
    }
    .status-pill:has(.dot.active) { --c: var(--green); --t: var(--green-t); }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--c); flex: none; }
    .dot.active { animation: pulse 2s ease-out infinite; }
    @keyframes pulse { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--c) 55%, transparent); } 70%, 100% { box-shadow: 0 0 0 7px transparent; } }
    .coords { font-size: 13px; color: var(--label2); cursor: pointer; white-space: nowrap; margin-left: auto; transition: color .2s; }
    .coords:hover { color: var(--blue); }
    #err { font-size: 13px; color: var(--red); line-height: 1.35; }
    #err:empty { display: none; }

    /* ---------- Segmented con indicador deslizante ---------- */
    .segmented { position: relative; display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; padding: 3px; height: 38px; border-radius: 999px; background: var(--well); }
    .thumb {
      position: absolute; top: 3px; bottom: 3px; left: 0; border-radius: 999px; background: var(--thumb); pointer-events: none;
      box-shadow: 0 2px 8px rgba(0,0,0,.14), inset 0 1px 0 rgba(255,255,255,.9);
      transition: transform .45s var(--spring), width .3s var(--ease);
    }
    .seg-opt {
      position: relative; z-index: 1; border: 0; background: transparent; border-radius: 999px; cursor: pointer;
      font: 500 13.5px var(--font); color: var(--label); transition: font-weight .2s, color .2s;
    }
    .seg-opt.active { font-weight: 600; }

    /* ---------- Secciones ---------- */
    .section { interpolate-size: allow-keywords; }
    .section summary { list-style: none; display: flex; align-items: center; gap: 10px; min-height: 50px; padding: 0 16px; font-size: 15px; font-weight: 600; cursor: pointer; }
    .section summary::-webkit-details-marker { display: none; }
    .section summary::after {
      content: ""; width: 8px; height: 14px; background: var(--label2); transition: transform .4s var(--spring);
      -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 8 14'%3E%3Cpath d='M1.5 1.5 6.5 7l-5 5.5' fill='none' stroke='black' stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center / contain no-repeat;
              mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 8 14'%3E%3Cpath d='M1.5 1.5 6.5 7l-5 5.5' fill='none' stroke='black' stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center / contain no-repeat;
    }
    .section[open] summary::after { transform: rotate(90deg); }
    .section::details-content { height: 0; overflow: hidden; transition: height .4s var(--ease), content-visibility .4s allow-discrete; }
    .section[open]::details-content { height: auto; }
    .sec-sub { margin-left: auto; font-size: 13px; font-weight: 400; color: var(--label2); }
    .sec-body { padding: 2px 14px 14px; display: flex; flex-direction: column; gap: 10px; }

    /* ---------- Lista tipo Ajustes ---------- */
    .list { border-radius: var(--r-ctrl); background: var(--g-ctrl); box-shadow: var(--hl); }
    .cell { position: relative; display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 46px; padding: 0 14px; font-size: 15px; }
    .cell + .cell::before { content: ""; position: absolute; top: 0; left: 14px; right: 0; height: .5px; background: var(--sep); }
    .cell.slider { min-height: 38px; padding-bottom: 4px; }
    label.cell { cursor: pointer; }
    .val { padding: 4px 11px; border-radius: 999px; background: var(--well); font-size: 14px; font-weight: 600; }

    .switch { position: relative; width: 51px; height: 31px; flex: none; }
    .switch input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; z-index: 2; }
    .switch i { position: absolute; inset: 0; border-radius: 999px; background: rgba(120,120,128,.32); transition: background .3s var(--ease); }
    .switch i::after {
      content: ""; position: absolute; top: 2px; left: 2px; width: 27px; height: 27px; border-radius: 999px; background: #fff;
      box-shadow: 0 3px 8px rgba(0,0,0,.15), 0 1px 1px rgba(0,0,0,.16);
      transition: transform .4s var(--spring), width .2s var(--ease);
    }
    .switch input:checked + i { background: var(--green); }
    .switch input:checked + i::after { transform: translateX(20px); }
    .switch input:active + i::after { width: 34px; }
    .switch input:checked:active + i::after { transform: translateX(13px); }
    .switch input:focus-visible + i { outline: 3px solid rgba(0,122,255,.45); outline-offset: 2px; }

    input[type=range] { -webkit-appearance: none; appearance: none; width: 100%; height: 28px; margin: 0; background: transparent; cursor: pointer; --p: 30%; }
    input[type=range]::-webkit-slider-runnable-track { height: 4px; border-radius: 2px; background: linear-gradient(90deg, var(--blue) var(--p), rgba(120,120,128,.32) var(--p)); }
    input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none; width: 28px; height: 28px; margin-top: -12px; border-radius: 50%; background: #fff;
      box-shadow: 0 2px 8px rgba(0,0,0,.25), 0 0 0 .5px rgba(0,0,0,.06); transition: transform .3s var(--spring);
    }
    input[type=range]:active::-webkit-slider-thumb { transform: scale(1.1); }

    .field {
      height: 40px; padding: 0 14px; border: 0; border-radius: 999px; background: var(--g-ctrl); box-shadow: var(--hl);
      font: 400 15px var(--font); color: var(--label); outline: 0; min-width: 0; transition: box-shadow .2s var(--ease);
    }
    .field:focus { box-shadow: var(--hl), 0 0 0 3px rgba(0,122,255,.3); }
    select.field {
      -webkit-appearance: none; appearance: none; padding-right: 32px; background-repeat: no-repeat; background-position: right 13px center;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='16' viewBox='0 0 10 16'%3E%3Cpath d='M2 6l3-3 3 3M2 10l3 3 3-3' fill='none' stroke='%238e8e93' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    }
    .caption { font-size: 12px; color: var(--label2); padding: 0 2px; }

    #btn-toggle-bar {
      position: fixed; top: 14px; left: 14px; z-index: 900; height: 40px; padding: 0 18px; border: 0; border-radius: 999px;
      font: 600 15px var(--font); color: var(--label); background: var(--g-panel); cursor: pointer;
      -webkit-backdrop-filter: blur(var(--g-blur)) saturate(var(--g-sat)); backdrop-filter: blur(var(--g-blur)) saturate(var(--g-sat));
      box-shadow: var(--shadow), var(--hl); transition: transform .35s var(--spring);
    }
    #btn-toggle-bar:active { transform: scale(.96); }

    /* ---------- Leaflet ---------- */
    .leaflet-control-zoom { margin: 14px 14px 0 0 !important; }
    .leaflet-bar { position: relative; border: 0 !important; border-radius: 20px !important; overflow: hidden; background: var(--g-panel) !important;
      -webkit-backdrop-filter: blur(20px) saturate(180%); backdrop-filter: blur(20px) saturate(180%); box-shadow: var(--shadow), var(--hl) !important; }
    .leaflet-bar a { background: transparent !important; color: var(--label) !important; border-bottom: .5px solid var(--sep) !important; width: 40px !important; height: 40px !important; line-height: 40px !important; }
    .leaflet-bar a:last-child { border-bottom: 0 !important; }

    /* ---------- Accesibilidad ---------- */
    @media (prefers-reduced-transparency: reduce) {
      :root { --g-panel: rgba(246,246,248,.97); --g-card: rgba(255,255,255,.7); --g-ctrl: rgba(255,255,255,.92); --g-blur: 0px; }
      #sidebar-shell, #btn-toggle-bar, .leaflet-bar { -webkit-backdrop-filter: none; backdrop-filter: none; }
    }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition-duration: .01ms !important; } }
    @media (prefers-contrast: more) {
      :root { --sep: rgba(60,60,67,.55); --label2: rgba(60,60,67,.95); }
      .card, .section, .search-wrap, .list { outline: 1px solid var(--sep); }
    }
    :root { color-scheme: light; }
    .btn { padding: 0 14px; font-size: 14.5px; }
    .glass-cv { position: absolute; inset: 0; width: 100%; height: 100%; border-radius: inherit; pointer-events: none; z-index: 0; }
    #sidebar-shell.gl, #sidebar-shell.gl.refract { background: rgba(255,255,255,.04); -webkit-backdrop-filter: none; backdrop-filter: none; }
    #sidebar-shell.gl::after { display: none; }
    #sidebar-shell.gl .card, #sidebar-shell.gl .section { background: rgba(255,255,255,.26); }
    .dpad { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
    .dpad .btn { padding: 0; font-size: 18px; }
    .hist-cell { cursor: pointer; font-size: 13px; }
    .toast { position: fixed; bottom: 22px; left: 50%; transform: translate(-50%, 20px); opacity: 0; pointer-events: none; z-index: 3000; max-width: 80vw; padding: 10px 18px; border-radius: 999px; background: var(--pop); box-shadow: var(--shadow); font-size: 13px; transition: transform .35s var(--spring), opacity .25s; }
    .toast.show { opacity: 1; transform: translate(-50%, 0); }
    .wizard { position: fixed; inset: 0; z-index: 4000; display: grid; place-items: center; background: rgba(0,0,0,.18); -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px); }
    .wizard[hidden] { display: none; }
    .wiz-card { width: min(420px, calc(100vw - 32px)); padding: 24px; border-radius: var(--r-panel); background: var(--pop); box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 14px; }
    .wiz-card h2 { margin: 0; font-size: 22px; letter-spacing: -.02em; }
    .wiz-steps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
    .wiz-steps li { display: flex; align-items: center; gap: 12px; font-size: 14px; }
    .wiz-steps li span { flex: 1; }
    .wiz-steps i { width: 22px; height: 22px; border-radius: 50%; flex: none; background: var(--well); transition: background .3s; }
    .wiz-steps li.ok i { background: var(--green); }
    .wiz-steps li.bad i { background: var(--red); }
    .hdg { display: flex; gap: 8px; align-items: center; }
    .hdg .arr { display: inline-block; transition: transform .3s var(--spring); }
    .wiz-note { margin: 0; font-size: 12.5px; color: var(--label2); }
  </style>
</head>
<body>
  <svg width="0" height="0" style="position:absolute" aria-hidden="true">
    <filter id="liquid" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
      <feTurbulence type="fractalNoise" baseFrequency="0.008 0.012" numOctaves="2" seed="4" result="n" />
      <feDisplacementMap in="SourceGraphic" in2="n" scale="14" xChannelSelector="R" yChannelSelector="G" />
    </filter>
  </svg>

  <div id="map-wrap"><div id="map"></div></div>

  <button id="btn-toggle-bar" type="button" style="display: none;">Simulador GPS</button>

  <aside id="sidebar-shell">
    <div id="sidebar-scroll">
      <div class="header">
        <span class="app-title">Simulador GPS</span>
        <span><button id="btn-help" class="btn btn-plain" type="button">Ayuda</button><button id="btn-hide-bar" class="btn btn-plain" type="button">Ocultar</button></span>
      </div>

      <div class="search-wrap">
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true"><circle cx="9" cy="9" r="5.5"/><path d="M13.5 13.5 17 17"/></svg>
        <input id="search-input" type="text" placeholder="Dirección o lat, lon" autocomplete="off" />
        <button id="btn-search" class="search-go" type="button" aria-label="Ir">
          <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10h12M11 5l5 5-5 5"/></svg>
        </button>
        <div id="suggest-list"></div>
      </div>

      <div class="card">
        <div class="card-head">
          <span class="card-title">Idioma</span>
          <span class="sec-sub">ES / EN</span>
        </div>
        <div class="segmented">
          <button id="lang-es" class="seg-opt active" type="button">Español</button>
          <button id="lang-en" class="seg-opt" type="button">English</button>
        </div>
      </div>

      <div class="card">
        <div class="status-line">
          <div class="status-pill"><span id="status-dot" class="dot"></span><span id="status-badge">Detenido</span></div>
          <span id="coords" class="coords">25.686600, -100.316100</span>
        </div>
        <div id="hdg" class="caption hdg"></div>
        <div class="row">
          <button id="btn-start" class="btn btn-primary grow" type="button">Iniciar</button>
          <button id="btn-stop" class="btn btn-stop grow" type="button">Detener</button>
        </div>
        <button id="btn-restore" class="btn btn-plain" type="button">Restaurar ubicación real</button>
        <div class="segmented">
          <button id="btn-layer-map" class="seg-opt active" type="button">Mapa</button>
          <button id="btn-layer-sat" class="seg-opt" type="button">Satélite</button>
        </div>
        <div id="err"></div>
      </div>

      <details class="section" open>
        <summary><span>Transporte y ruta</span><span id="route-info" class="sec-sub">Carro · 0 pts</span></summary>
        <div class="sec-body">
          <div class="segmented">
            <button id="btn-mode-walk" class="seg-opt" type="button">Caminata</button>
            <button id="btn-mode-bike" class="seg-opt" type="button">Bici</button>
            <button id="btn-mode-car" class="seg-opt active" type="button">Carro</button>
          </div>
          <button id="btn-route-mode" class="btn" type="button">Marcar puntos</button>
          <div class="row">
            <button id="btn-route-undo" class="btn grow" type="button">Deshacer</button>
            <button id="btn-route-clear" class="btn btn-stop grow" type="button">Limpiar</button>
          </div>
          <div class="row">
            <button id="btn-route-run" class="btn btn-primary grow" type="button">Iniciar ruta</button>
            <button id="btn-route-pause" class="btn grow" type="button">Pausar</button>
          </div>
          <div class="row">
            <button id="btn-gpx-import" class="btn grow" type="button">Importar GPX</button>
            <button id="btn-gpx-export" class="btn grow" type="button">Exportar GPX</button>
            <input id="gpx-file" type="file" accept=".gpx" hidden />
          </div>
          <div class="list">
            <div class="cell"><span>Velocidad</span><span id="speed-val" class="val">45 km/h</span></div>
            <div class="cell slider"><input id="route-speed" type="range" min="1" max="120" step="1" value="45" aria-label="Velocidad en km/h" /></div>
            <label class="cell"><span>Calles</span><span class="switch"><input id="route-streets" type="checkbox" role="switch" checked /><i></i></span></label>
            <label class="cell"><span>Variación</span><span class="switch"><input id="route-jitter" type="checkbox" role="switch" checked /><i></i></span></label>
            <label class="cell"><span>Bucle</span><span class="switch"><input id="route-loop" type="checkbox" role="switch" /><i></i></span></label>
            <div class="cell"><span>Parada en cada punto</span><span id="dwell-val" class="val">0 s</span></div>
            <div class="cell slider"><input id="route-dwell" type="range" min="0" max="300" step="5" value="0" aria-label="Parada en segundos" /></div>
          </div>
          <div id="route-stats" class="caption">0 m · ~0 min · auto</div>
        </div>
      </details>

      <details class="section">
        <summary><span>Favoritos</span><span id="summary-favs" class="sec-sub">0</span></summary>
        <div class="sec-body">
          <input id="fav-folder" class="field" list="fav-folders" type="text" placeholder="Carpeta (opcional)" /><datalist id="fav-folders"></datalist>
          <div class="row">
            <input id="fav-name" class="field grow" type="text" placeholder="Nombre del lugar" />
            <button id="btn-fav-save" class="btn btn-primary" type="button">Guardar</button>
          </div>
          <div class="row">
            <select id="fav-select" class="field grow"><option value="">Elegir favorito…</option></select>
            <button id="btn-fav-go" class="btn" type="button">Ir</button>
            <button id="btn-fav-del" class="btn btn-stop" type="button">Borrar</button>
          </div>
          <div class="row"><button id="btn-fav-import" class="btn grow" type="button">Importar</button><button id="btn-fav-export" class="btn grow" type="button">Exportar</button><input id="fav-file" type="file" accept=".json" hidden /></div>
        </div>
      </details>

      <details class="section" id="hist-sec">
        <summary><span>Historial</span><span id="summary-hist" class="sec-sub">0</span></summary>
        <div class="sec-body">
          <button id="btn-undo-tp" class="btn" type="button">Volver a la ubicación anterior</button>
          <div id="hist-list" class="list"></div>
        </div>
      </details>

      <details class="section">
        <summary><span>Controles y atajos</span><span id="summary-step" class="sec-sub">2 Normal</span></summary>
        <div class="sec-body">
          <div class="segmented">
            <button id="btn-step-1" class="seg-opt" type="button">1 Lento</button>
            <button id="btn-step-2" class="seg-opt active" type="button">2 Normal</button>
            <button id="btn-step-3" class="seg-opt" type="button">3 Rápido</button>
          </div>
          <div class="row">
            <button id="btn-center" class="btn grow" type="button">Centrar</button>
            <button id="btn-copy" class="btn grow" type="button">Copiar</button>
          </div>
          <div class="list">
            <label class="cell"><span>Seguir marcador</span><span class="switch"><input id="follow-marker" type="checkbox" role="switch" /><i></i></span></label>
          </div>
          <div class="dpad">
            <button class="btn" data-k="w" type="button" aria-label="Norte">↑</button>
            <button class="btn" data-k="s" type="button" aria-label="Sur">↓</button>
            <button class="btn" data-k="a" type="button" aria-label="Oeste">←</button>
            <button class="btn" data-k="d" type="button" aria-label="Este">→</button>
          </div>
          <div class="caption">WASD mover · 1/2/3 paso · Espacio pausa</div>
          <div class="caption">Ctrl+Alt+P pausa · Ctrl+Alt+R restaurar · Ctrl+Alt+↑↓←→ mover (global)</div>
        </div>
      </details>
    </div>
  </aside>

  <div id="toast" class="toast" role="status"></div>
  <div id="wizard" class="wizard" hidden>
    <div class="wiz-card">
      <h2>Conecta tu iPhone</h2>
      <ol class="wiz-steps">
        <li id="w-admin"><i></i><span>Ejecuta la app como administrador</span><button id="btn-elevate" class="btn btn-plain" type="button" hidden>Reiniciar</button></li>
        <li id="w-dev"><i></i><span>Conecta el iPhone por USB y toca <b>Confiar</b></span></li>
        <li id="w-mode"><i></i><span>Activa el Modo de desarrollador en Ajustes → Privacidad y seguridad</span></li>
      </ol>
      <p class="wiz-note">Algunos juegos y apps prohíben alterar la ubicación y pueden suspender cuentas. Úsalo bajo tu responsabilidad.</p>
      <button id="btn-wiz-ok" class="btn btn-primary" type="button">Entendido</button>
    </div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    document.addEventListener("DOMContentLoaded", () => {
      let lat = 25.6866, lon = -100.3161;
      let addingWaypoints = false;
      let waypoints = [];
      let pathPoints = [];
      let waypointMarkers = [];
      let routeLine = null;
      let favorites = [];
      let suggestTimer = null;
      let moveStep = 0.0002;
      let routePaused = false;
      let simMode = "car";
      let mapMode = "map";
      let activeRouteLabel = "auto";

      const modePresets = {
        walk: { label: "Caminata", speed: 5, stepLevel: 1 },
        bike: { label: "Bici", speed: 18, stepLevel: 2 },
        car:  { label: "Carro", speed: 45, stepLevel: 3 }
      };

      const stepPresets = {
        1: { value: 0.00008, label: "1 Lento" },
        2: { value: 0.0002,  label: "2 Normal" },
        3: { value: 0.0005,  label: "3 Rápido" }
      };

      if (typeof L === "undefined") {
        document.getElementById("err").textContent = "Error al cargar Leaflet.";
        return;
      }

      const osmLayer = L.tileLayer("{{ tiles_map|safe }}", {
        maxZoom: 19, crossOrigin: "anonymous"
      });
      const satLayer = L.tileLayer(
        "{{ tiles_sat|safe }}",
        { maxZoom: 19, crossOrigin: "anonymous" }
      );
      const satLabelsLayer = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19, crossOrigin: "anonymous" }
      );

      const map = L.map("map", { layers: [osmLayer], zoomControl: false }).setView([lat, lon], 15);
      L.control.zoom({ position: "topright" }).addTo(map);
      window.__map = map;
      const marker = L.marker([lat, lon], { draggable: true }).addTo(map);
      setTimeout(() => map.invalidateSize(), 150);

      function syncMapLayer() {
        [osmLayer, satLayer, satLabelsLayer].forEach(layer => {
          if (map.hasLayer(layer)) map.removeLayer(layer);
        });
        if (mapMode === "sat") {
          map.addLayer(satLayer);
          map.addLayer(satLabelsLayer);
        } else {
          map.addLayer(osmLayer);
        }
      }

      function setStepLevel(level) {
        const preset = stepPresets[level];
        if (!preset) return;
        moveStep = preset.value;
        document.getElementById("btn-step-1").classList.toggle("active", level === 1);
        document.getElementById("btn-step-2").classList.toggle("active", level === 2);
        document.getElementById("btn-step-3").classList.toggle("active", level === 3);
        document.getElementById("summary-step").textContent = preset.label;
      }

      document.getElementById("btn-step-1").onclick = () => setStepLevel(1);
      document.getElementById("btn-step-2").onclick = () => setStepLevel(2);
      document.getElementById("btn-step-3").onclick = () => setStepLevel(3);

      function updateModeSummary() {
        const label = modePresets[simMode] ? modePresets[simMode].label : "Modo";
        document.getElementById("route-info").textContent = `${label} · ${waypoints.length} pts`;
      }

      function applySimMode(mode) {
        const preset = modePresets[mode];
        if (!preset) return;
        simMode = mode;
        setStepLevel(preset.stepLevel);
        document.getElementById("btn-mode-walk").classList.toggle("active", mode === "walk");
        document.getElementById("btn-mode-bike").classList.toggle("active", mode === "bike");
        document.getElementById("btn-mode-car").classList.toggle("active", mode === "car");
        document.getElementById("route-speed").value = String(preset.speed);
        document.getElementById("route-speed").dispatchEvent(new Event("input"));
        updateModeSummary();
        redrawRoute();
      }

      document.getElementById("btn-mode-walk").onclick = () => applySimMode("walk");
      document.getElementById("btn-mode-bike").onclick = () => applySimMode("bike");
      document.getElementById("btn-mode-car").onclick = () => applySimMode("car");

      function setMapMode(mode) {
        mapMode = mode;
        document.getElementById("btn-layer-map").classList.toggle("active", mode === "map");
        document.getElementById("btn-layer-sat").classList.toggle("active", mode === "sat");
        syncMapLayer();
      }

      document.getElementById("btn-layer-map").onclick = () => setMapMode("map");
      document.getElementById("btn-layer-sat").onclick = () => setMapMode("sat");

      function syncSidebarVisibility(hidden) {
        const sb = document.getElementById("sidebar-shell");
        const showBtn = document.getElementById("btn-toggle-bar");
        sb.classList.toggle("collapsed", hidden);
        showBtn.style.display = hidden ? "block" : "none";
      }

      document.getElementById("btn-hide-bar").onclick = () => syncSidebarVisibility(true);
      document.getElementById("btn-toggle-bar").onclick = () => syncSidebarVisibility(false);

      function updateLabel() {
        document.getElementById("coords").textContent = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
      }

      function sendMove(syncRemote = true) {
        marker.setLatLng([lat, lon]);
        updateLabel();
        if (document.getElementById("follow-marker").checked) {
          map.panTo([lat, lon], { animate: true, duration: 0.25 });
        }
        if (syncRemote) {
          fetch("/move", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lat, lon })
          }).catch(() => {});
        }
      }

      function distMeters(a, b) {
        const r = 6371000;
        const p1 = a.lat * Math.PI / 180;
        const p2 = b.lat * Math.PI / 180;
        const dp = (b.lat - a.lat) * Math.PI / 180;
        const dl = (b.lon - a.lon) * Math.PI / 180;
        const x = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
        return 2 * r * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
      }

      function polylineLengthMeters(pts) {
        let total = 0;
        for (let i = 0; i < pts.length - 1; i++) {
          total += distMeters(pts[i], pts[i + 1]);
        }
        return total;
      }

      function updateRouteStats(pts) {
        const activePts = (pts && pts.length >= 2) ? pts : waypoints;
        const totalM = polylineLengthMeters(activePts);
        const speedKmh = Math.max(1, parseFloat(document.getElementById("route-speed").value) || 15);
        const speedMps = (speedKmh * 1000) / 3600;
        const sec = totalM / speedMps;
        const distText = totalM >= 1000 ? `${(totalM / 1000).toFixed(2)} km` : `${Math.round(totalM)} m`;
        const timeText = sec >= 60 ? `${(sec / 60).toFixed(1)} min` : `${Math.round(sec)} s`;
        document.getElementById("route-stats").textContent = `${distText} · ~${timeText} · ${activeRouteLabel}`;
      }

      async function fetchOsrmRoutes(coordsStr, profile) {
        const url = `https://router.project-osrm.org/route/v1/${profile}/${coordsStr}?overview=full&alternatives=true&geometries=geojson`;
        const resp = await fetch(url);
        if (!resp.ok) return [];
        const data = await resp.json();
        if (!data || !Array.isArray(data.routes)) return [];
        return data.routes
          .map(r => ({
            duration: r.duration || 0,
            distance: r.distance || 0,
            pts: (r.geometry && Array.isArray(r.geometry.coordinates))
              ? r.geometry.coordinates.map(c => ({ lat: c[1], lon: c[0] }))
              : []
          }))
          .filter(r => r.pts.length >= 2);
      }

      function offsetDetourPts(pts, metersOffset, sign) {
        if (pts.length < 2) return pts.slice();
        const out = [pts[0]];
        const n = pts.length - 1;
        for (let i = 1; i < n; i++) {
          const prev = pts[i - 1];
          const cur = pts[i];
          const next = pts[i + 1];
          const dx = next.lon - prev.lon;
          const dy = next.lat - prev.lat;
          const len = Math.hypot(dx, dy) || 1;
          const nx = -dy / len;
          const ny = dx / len;
          const env = Math.sin((i / n) * Math.PI);
          const dLat = (metersOffset * env * sign) / 111320;
          const dLon = (metersOffset * env * sign) / (111320 * Math.max(0.2, Math.cos(cur.lat * Math.PI / 180)));
          out.push({ lat: cur.lat + ny * dLat, lon: cur.lon + nx * dLon });
        }
        out.push(pts[n]);
        return out;
      }

      async function buildPathFromWaypoints() {
        if (waypoints.length < 2) {
          pathPoints = waypoints.slice();
          activeRouteLabel = "recta";
          updateRouteStats(pathPoints);
          return pathPoints;
        }
        if (!document.getElementById("route-streets").checked) {
          pathPoints = waypoints.slice();
          activeRouteLabel = "recta";
          updateRouteStats(pathPoints);
          return pathPoints;
        }

        const coordsStr = waypoints.map(p => `${p.lon},${p.lat}`).join(";");
        let drivingRoutes = [];
        let modeRoutes = [];

        try { drivingRoutes = await fetchOsrmRoutes(coordsStr, "driving"); } catch (_) {}
        if (simMode === "walk") {
          try { modeRoutes = await fetchOsrmRoutes(coordsStr, "foot"); } catch (_) {}
        } else if (simMode === "bike") {
          try { modeRoutes = await fetchOsrmRoutes(coordsStr, "bike"); } catch (_) {}
        }

        if (modeRoutes.length > 0) {
          const sorted = modeRoutes.slice().sort((a, b) => (a.distance - b.distance) || (a.duration - b.duration));
          const picked = simMode === "bike" && sorted.length > 1 ? sorted[1] : sorted[0];
          pathPoints = picked.pts;
          activeRouteLabel = simMode === "walk" ? "peatonal" : "bici";
          updateRouteStats(pathPoints);
          return pathPoints;
        }

        if (drivingRoutes.length > 0) {
          const bestCar = drivingRoutes.slice().sort((a, b) => (a.duration - b.duration) || (a.distance - b.distance))[0];
          if (simMode === "car") {
            pathPoints = bestCar.pts;
            activeRouteLabel = "auto";
            updateRouteStats(pathPoints);
            return pathPoints;
          }
          const altDifferent = drivingRoutes.find(r => Math.abs(r.distance - bestCar.distance) > 25);
          if (altDifferent) {
            pathPoints = altDifferent.pts;
            activeRouteLabel = simMode === "walk" ? "caminata alt" : "bici alt";
            updateRouteStats(pathPoints);
            return pathPoints;
          }
          const detourMeters = simMode === "walk" ? -28 : 45;
          const sign = simMode === "walk" ? -1 : 1;
          const adjusted = offsetDetourPts(bestCar.pts, detourMeters, sign);
          const snapped = await fetchOsrmRoutes(adjusted.map(p => `${p.lon},${p.lat}`).join(";"), "driving");
          if (snapped.length > 0) {
            pathPoints = snapped[0].pts;
            activeRouteLabel = simMode === "walk" ? "caminata" : "bici";
            updateRouteStats(pathPoints);
            return pathPoints;
          }
          pathPoints = adjusted;
          activeRouteLabel = simMode === "walk" ? "caminata" : "bici";
          updateRouteStats(pathPoints);
          return pathPoints;
        }

        pathPoints = waypoints.slice();
        activeRouteLabel = "recta";
        updateRouteStats(pathPoints);
        return pathPoints;
      }

      function redrawRoute() {
        waypointMarkers.forEach(m => map.removeLayer(m));
        waypointMarkers = [];
        if (routeLine) {
          map.removeLayer(routeLine);
          routeLine = null;
        }
        waypoints.forEach((pt, idx) => {
          const wm = L.circleMarker([pt.lat, pt.lon], {
            radius: 5,
            color: "#ffffff",
            fillColor: "#007aff",
            fillOpacity: 1,
            weight: 2
          }).addTo(map);
          wm.bindTooltip(`${idx + 1}`);
          waypointMarkers.push(wm);
        });
        updateModeSummary();
        if (waypoints.length >= 2) {
          const lineColor = simMode === "walk" ? "#28cd41" : (simMode === "bike" ? "#ff9f0a" : "#007aff");
          routeLine = L.polyline(waypoints.map(p => [p.lat, p.lon]), {
            color: lineColor,
            weight: 4
          }).addTo(map);
          buildPathFromWaypoints().then(pts => {
            if (pts && pts.length >= 2 && routeLine) {
              routeLine.setLatLngs(pts.map(p => [p.lat, p.lon]));
            }
          }).catch(() => {});
        } else {
          updateRouteStats([]);
        }
      }

      function stopIndexes(pts) {
        const out = []; let from = 0;
        waypoints.forEach((w, k) => {
          if (k === 0) return;
          let best = from, bd = Infinity;
          for (let i = from; i < pts.length; i++) { const d = distMeters(w, pts[i]); if (d < bd) { bd = d; best = i; } }
          out.push(best); from = best;
        });
        return out;
      }
      window.__api = { reloadFavorites: loadFavoritesFromServer, map, getPath: () => pathPoints, getWaypoints: () => waypoints, setWaypoints: pts => { waypoints = pts; redrawRoute(); }, setLatLon: (a, b) => applyLocation(a, b) };
      document.getElementById("route-streets").addEventListener("change", redrawRoute);
      document.getElementById("route-speed").addEventListener("input", () => updateRouteStats(pathPoints));

      function hideSuggestions() {
        const box = document.getElementById("suggest-list");
        box.style.display = "none";
        box.innerHTML = "";
      }

      function applyLocation(newLat, newLon, labelText = "") {
        lat = parseFloat(newLat);
        lon = parseFloat(newLon);
        map.setView([lat, lon], 16);
        sendMove(true);
        if (labelText) {
          document.getElementById("search-input").value = labelText;
        }
        hideSuggestions();
      }

      function renderSuggestions(items) {
        const box = document.getElementById("suggest-list");
        box.innerHTML = "";
        if (!items || items.length === 0) {
          box.style.display = "none";
          return;
        }
        items.forEach(item => {
          const div = document.createElement("div");
          div.className = "suggest-item";
          div.textContent = item.label;
          div.onclick = () => applyLocation(item.lat, item.lon, item.label);
          box.appendChild(div);
        });
        box.style.display = "block";
      }

      function renderFavorites() {
        const sel = document.getElementById("fav-select");
        sel.innerHTML = '<option value="">Elegir favorito…</option>';
        const dl = document.getElementById("fav-folders"), groups = {};
        dl.innerHTML = "";
        favorites.forEach((f, i) => {
          let parent = sel;
          if (f.folder) {
            if (!groups[f.folder]) {
              groups[f.folder] = sel.appendChild(Object.assign(document.createElement("optgroup"), { label: f.folder }));
              dl.appendChild(Object.assign(document.createElement("option"), { value: f.folder }));
            }
            parent = groups[f.folder];
          }
          const opt = document.createElement("option");
          opt.value = String(i);
          opt.textContent = f.name;
          parent.appendChild(opt);
        });
        document.getElementById("summary-favs").textContent = String(favorites.length);
      }

      function loadFavoritesFromServer() {
        fetch("/favorites").then(r => r.json()).then(d => {
          favorites = d.favorites || [];
          renderFavorites();
        }).catch(() => {});
      }

      document.getElementById("search-input").addEventListener("input", (e) => {
        const q = e.target.value.trim();
        if (suggestTimer) clearTimeout(suggestTimer);
        if (q.length < 3) {
          hideSuggestions();
          return;
        }
        suggestTimer = setTimeout(() => {
          fetch(`/suggest?q=${encodeURIComponent(q)}`)
            .then(r => r.json())
            .then(d => renderSuggestions(d.results || []))
            .catch(() => hideSuggestions());
        }, 600);
      });

      document.getElementById("search-input").addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          document.getElementById("btn-search").click();
        }
      });

      document.addEventListener("click", (e) => {
        if (!e.target.closest(".search-wrap")) {
          hideSuggestions();
        }
      });

      map.on("click", (e) => {
        lat = e.latlng.lat;
        lon = e.latlng.lng;
        sendMove(true);
        if (addingWaypoints) {
          waypoints.push({ lat, lon });
          redrawRoute();
        }
      });

      marker.on("dragend", (e) => {
        const p = e.target.getLatLng();
        lat = p.lat;
        lon = p.lng;
        sendMove(true);
      });

      document.getElementById("btn-center").onclick = () => {
        map.setView([lat, lon], Math.max(map.getZoom(), 16));
      };

      function copyCoords() {
        const txt = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(txt).catch(() => {});
        }
      }

      document.getElementById("btn-copy").onclick = copyCoords;
      document.getElementById("coords").onclick = copyCoords;

      document.getElementById("btn-start").onclick = () => {
        fetch("/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lat, lon })
        }).catch(() => {});
      };

      document.getElementById("btn-stop").onclick = () => {
        routePaused = false;
        fetch("/stop", { method: "POST" }).catch(() => {});
      };

      document.getElementById("btn-search").onclick = () => {
        const q = document.getElementById("search-input").value.trim();
        if (!q) return;
        fetch("/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q })
        }).then(r => r.json()).then(d => {
          if (d.ok) {
            applyLocation(d.lat, d.lon);
          }
        }).catch(() => {});
      };

      document.getElementById("btn-fav-save").onclick = () => {
        const name = document.getElementById("fav-name").value.trim() || `Punto ${favorites.length + 1}`;
        fetch("/favorites", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, lat, lon, folder: document.getElementById("fav-folder").value.trim() })
        }).then(r => r.json()).then(d => {
          favorites = d.favorites || [];
          renderFavorites();
          document.getElementById("fav-name").value = "";
        }).catch(() => {});
      };

      document.getElementById("btn-fav-go").onclick = () => {
        const idx = parseInt(document.getElementById("fav-select").value, 10);
        if (!isNaN(idx) && favorites[idx]) {
          applyLocation(favorites[idx].lat, favorites[idx].lon);
        }
      };

      document.getElementById("btn-fav-del").onclick = () => {
        const idx = parseInt(document.getElementById("fav-select").value, 10);
        if (isNaN(idx)) return;
        fetch(`/favorites/${idx}`, { method: "DELETE" }).then(r => r.json()).then(d => {
          favorites = d.favorites || [];
          renderFavorites();
        }).catch(() => {});
      };

      document.getElementById("btn-route-mode").onclick = () => {
        addingWaypoints = !addingWaypoints;
        const btn = document.getElementById("btn-route-mode");
        btn.classList.toggle("btn-primary", addingWaypoints);
        btn.textContent = addingWaypoints ? "Marcando..." : "Marcar puntos";
      };

      document.getElementById("btn-route-undo").onclick = () => {
        if (waypoints.length > 0) {
          waypoints.pop();
          redrawRoute();
        }
      };

      document.getElementById("btn-route-run").onclick = async () => {
        if (waypoints.length < 2) return;
        addingWaypoints = false;
        routePaused = false;
        const btn = document.getElementById("btn-route-mode");
        btn.classList.remove("btn-primary");
        btn.textContent = "Marcar puntos";
        const pts = await buildPathFromWaypoints();
        const speedKmh = parseFloat(document.getElementById("route-speed").value) || 15;
        const loop = document.getElementById("route-loop").checked;
        const jitter = document.getElementById("route-jitter").checked;
        fetch("/route/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ waypoints: pts, speed_kmh: speedKmh, loop, jitter, dwell: parseFloat(document.getElementById("route-dwell").value) || 0, stops: stopIndexes(pts) })
        }).catch(() => {});
      };

      document.getElementById("btn-route-pause").onclick = () => {
        routePaused = !routePaused;
        document.getElementById("btn-route-pause").textContent = routePaused ? "Reanudar" : "Pausar";
        if (routePaused) {
          fetch("/route/pause", { method: "POST" }).catch(() => {});
        } else if (pathPoints.length >= 2) {
          const speedKmh = parseFloat(document.getElementById("route-speed").value) || 15;
          const loop = document.getElementById("route-loop").checked;
          const jitter = document.getElementById("route-jitter").checked;
          fetch("/route/resume", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ speed_kmh: speedKmh, loop, jitter })
          }).catch(() => {});
        }
      };

      document.getElementById("btn-route-clear").onclick = () => {
        waypoints = [];
        pathPoints = [];
        routePaused = false;
        document.getElementById("btn-route-pause").textContent = "Pausar";
        redrawRoute();
        fetch("/route/clear", { method: "POST" }).catch(() => {});
      };

      document.addEventListener("keydown", (e) => {
        const tag = document.activeElement ? document.activeElement.tagName : "";
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        if (e.key === "1") { setStepLevel(1); return; }
        if (e.key === "2") { setStepLevel(2); return; }
        if (e.key === "3") { setStepLevel(3); return; }
        if (e.code === "Space") {
          e.preventDefault();
          document.getElementById("btn-route-pause").click();
          return;
        }
        if (e.key === "w" || e.key === "W") { lat += moveStep; sendMove(true); }
        if (e.key === "s" || e.key === "S") { lat -= moveStep; sendMove(true); }
        if (e.key === "a" || e.key === "A") { lon -= moveStep; sendMove(true); }
        if (e.key === "d" || e.key === "D") { lon += moveStep; sendMove(true); }
      });

      window.addEventListener("beforeunload", () => {
        navigator.sendBeacon("/cleanup", "");
      });

      loadFavoritesFromServer();

      setInterval(() => {
        fetch("/status").then(r => r.json()).then(d => {
          const badge = document.getElementById("status-badge");
          const dot = document.getElementById("status-dot");
          badge.textContent = d.status_text;
          dot.classList.toggle("active", Boolean(d.active));
          document.getElementById("err").textContent = d.error ? d.error : "";
          if (d.route_running && typeof d.lat === "number" && typeof d.lon === "number") {
            lat = d.lat;
            lon = d.lon;
            marker.setLatLng([lat, lon]);
            updateLabel();
            if (document.getElementById("follow-marker").checked) {
              map.panTo([lat, lon], { animate: true, duration: 0.35 });
            }
          }
        }).catch(() => {});
      }, 500);
    });
  </script>
  <script>
    (() => {
      const $ = s => document.querySelector(s);
      const $$ = s => [...document.querySelectorAll(s)];
      const shell = $("#sidebar-shell");

      // Refracción SVG solo si el motor lo soporta y el usuario no pidió menos transparencia/movimiento
      const calm = matchMedia("(prefers-reduced-motion: reduce), (prefers-reduced-transparency: reduce)").matches;
      if (!calm && CSS.supports("backdrop-filter", "url(#liquid) blur(1px)")) shell.classList.add("refract");

      // Reflejo de luz que sigue al puntero
      shell.addEventListener("pointermove", e => {
        const r = shell.getBoundingClientRect();
        shell.style.setProperty("--mx", (e.clientX - r.left) + "px");
        shell.style.setProperty("--my", (e.clientY - r.top) + "px");
        mouse = [e.clientX - r.left, e.clientY - r.top]; glassDirty = true;
      });
      shell.addEventListener("pointerleave", () => { mouse = [-999, -999]; glassDirty = true; });

      // Segmented controls con indicador deslizante
      function place(seg) {
        const a = seg.querySelector(".seg-opt.active");
        const t = seg.querySelector(".thumb");
        if (!a || !t || !a.offsetWidth) return;
        const first = !t.style.width;
        if (first) t.style.transition = "none";
        t.style.width = a.offsetWidth + "px";
        t.style.transform = `translateX(${a.offsetLeft}px)`;
        if (first) { t.offsetWidth; t.style.transition = ""; }
      }
      $$(".segmented").forEach(seg => {
        const t = document.createElement("span");
        t.className = "thumb";
        seg.prepend(t);
        place(seg);
        new MutationObserver(() => place(seg)).observe(seg, { subtree: true, attributes: true, attributeFilter: ["class"] });
        new ResizeObserver(() => place(seg)).observe(seg);
      });

      // Slider de velocidad
      const sp = $("#route-speed"), sv = $("#speed-val");
      const syncSpeed = () => {
        sv.textContent = sp.value + " km/h";
        sp.style.setProperty("--p", ((sp.value - sp.min) / (sp.max - sp.min) * 100) + "%");
      };
      sp.addEventListener("input", syncSpeed);
      syncSpeed();

      // Soltar el foco tras usar el mouse para que WASD y 1/2/3 sigan funcionando
      sp.addEventListener("pointerup", () => sp.blur());
      $$(".switch input").forEach(i => i.addEventListener("click", e => { if (e.detail) i.blur(); }));

      // ---------- Liquid Glass WebGL: refracta los tiles del mapa ----------
      let mouse = [-999, -999], glassDirty = true, dead = false;
      const VS = "attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}";
      const FS = `precision highp float;
uniform sampler2D tx;uniform vec2 res,mouse;uniform float R,W,px;
float sdf(vec2 p){vec2 q=abs(p)-(res*.5-R);return length(max(q,0.))+min(max(q.x,q.y),0.)-R;}
vec3 blur(vec2 c,float rad){vec3 s=vec3(0.);for(int i=0;i<10;i++){float a=float(i)*2.39996,r=sqrt((float(i)+.5)/10.)*rad;s+=texture2D(tx,(c+vec2(cos(a),sin(a))*r)/res).rgb;}return s/10.;}
void main(){
  vec2 f=vec2(gl_FragCoord.x,res.y-gl_FragCoord.y),p=f-res*.5;
  float d=sdf(p),a=clamp(.5-d,0.,1.);
  if(a<=0.){gl_FragColor=vec4(0.);return;}
  vec2 n=normalize(vec2(sdf(p+vec2(1.,0.))-sdf(p-vec2(1.,0.)),sdf(p+vec2(0.,1.))-sdf(p-vec2(0.,1.)))+1e-5);
  float t=clamp(1.+d/W,0.,1.);
  vec2 o=-n*pow(t,2.2)*W*.9;
  float r=7.*px;
  vec3 c=vec3(blur(f+o*1.12,r).r,blur(f+o,r).g,blur(f+o*.88,r).b);
  c=mix(vec3(dot(c,vec3(.299,.587,.114))),c,1.3);
  c=mix(c,vec3(1.),.30);
  float lit=max(dot(n,normalize(vec2(-.55,-.83))),0.);
  float rim=1.-smoothstep(0.,2.5*px,-d);
  c+=rim*(.25+.7*lit)+pow(t,3.)*.18*(.4+lit);
  c+=.09*exp(-pow(length(f-mouse)/(170.*px),2.));
  gl_FragColor=vec4(c*a,a);
}`;

      function startGlass(map) {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const cv = document.createElement("canvas");
        cv.className = "glass-cv";
        shell.prepend(cv);
        const bail = e => { dead = true; console.warn("Liquid Glass desactivado:", e); cv.remove(); shell.classList.remove("gl"); };
        const gl = cv.getContext("webgl", { premultipliedAlpha: true, antialias: false });
        if (!gl) return bail("sin WebGL");
        let U;
        try {
          const mk = (ty, src) => {
            const s = gl.createShader(ty); gl.shaderSource(s, src); gl.compileShader(s);
            if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw gl.getShaderInfoLog(s);
            return s;
          };
          const pr = gl.createProgram();
          gl.attachShader(pr, mk(gl.VERTEX_SHADER, VS));
          gl.attachShader(pr, mk(gl.FRAGMENT_SHADER, FS));
          gl.linkProgram(pr); gl.useProgram(pr);
          gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
          const loc = gl.getAttribLocation(pr, "a");
          gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
          U = Object.fromEntries(["tx", "res", "mouse", "R", "W", "px"].map(n => [n, gl.getUniformLocation(pr, n)]));
        } catch (e) { return bail(e); }
        gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
        [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]
          .forEach(([k, v]) => gl.texParameteri(gl.TEXTURE_2D, k, v));

        const sc = document.createElement("canvas"), cx = sc.getContext("2d");
        let until = 0, ok = false;
        const mark = () => { glassDirty = true; };
        map.on("move zoom viewreset load resize layeradd layerremove", mark);
        map.on("zoomstart zoomanim movestart", () => { until = performance.now() + 700; });
        map.getContainer().addEventListener("load", mark, true);
        new ResizeObserver(mark).observe(shell);
        addEventListener("resize", mark);

        function render() {
          const w = shell.clientWidth, h = shell.clientHeight;
          if (!w || !h) return;
          if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
            cv.width = sc.width = Math.round(w * dpr);
            cv.height = sc.height = Math.round(h * dpr);
            gl.viewport(0, 0, cv.width, cv.height);
          }
          const L = shell.offsetLeft, T = shell.offsetTop;
          cx.setTransform(dpr, 0, 0, dpr, 0, 0);
          cx.fillStyle = "#e5e5ea"; cx.fillRect(0, 0, w, h);
          map.getContainer().querySelectorAll(".leaflet-tile").forEach(im => {
            if (!im.complete || !im.naturalWidth) return;
            const r = im.getBoundingClientRect();
            if (r.right < L || r.left > L + w || r.bottom < T || r.top > T + h) return;
            cx.drawImage(im, r.left - L, r.top - T, r.width + .5, r.height + .5);
          });
          try { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, sc); }
          catch (e) { return bail(e); }
          gl.uniform1i(U.tx, 0);
          gl.uniform2f(U.res, cv.width, cv.height);
          gl.uniform2f(U.mouse, mouse[0] * dpr, mouse[1] * dpr);
          gl.uniform1f(U.R, 32 * dpr); gl.uniform1f(U.W, 26 * dpr); gl.uniform1f(U.px, dpr);
          gl.drawArrays(gl.TRIANGLES, 0, 3);
          if (!ok) { ok = true; shell.classList.add("gl"); }
        }
        (function loop(now) {
          if (dead) return;
          requestAnimationFrame(loop);
          if (shell.classList.contains("collapsed")) return;
          if (glassDirty || now < until) { glassDirty = false; render(); }
        })(0);
      }
      document.addEventListener("DOMContentLoaded", () => { if (window.__map) startGlass(window.__map); });
    })();
  </script>
  <script>
    (() => {
      const $ = s => document.querySelector(s);
      const api = () => window.__api;
      const toast = m => { const t = $("#toast"); t.textContent = m; t.classList.add("show"); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("show"), 3500); };
      const post = (u, b) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) }).then(r => r.json());

      window.__ui = { toast, post };
      // Asistente de conexión
      const wiz = $("#wizard"), mark = (id, c) => { $(id).className = c; };
      const refresh = () => fetch("/status").then(r => r.json()).then(d => {
        mark("#w-admin", d.admin ? "ok" : "bad"); $("#btn-elevate").hidden = d.admin;
        mark("#w-dev", d.device ? "ok" : "");
        const dev = /DeveloperMode|InvalidService/.test(d.error || "");
        mark("#w-mode", dev ? "bad" : (d.device && d.active ? "ok" : ""));
      }).catch(() => {});
      setInterval(() => { if (!wiz.hidden) refresh(); }, 1000);
      const openWiz = () => { wiz.hidden = false; refresh(); };
      $("#btn-help").onclick = openWiz;
      $("#btn-wiz-ok").onclick = () => { wiz.hidden = true; try { localStorage.setItem("wiz_seen", "1"); } catch (_) {} };
      $("#btn-elevate").onclick = () => post("/elevate").then(d => { if (!d.ok) toast("No se pudo pedir permisos de administrador"); });
      try { if (!localStorage.getItem("wiz_seen")) openWiz(); } catch (_) { openWiz(); }
      $("#btn-restore").onclick = () => { $("#btn-stop").click(); toast("Ubicación real restaurada"); };

      // Historial
      let hist = [];
      const ago = t => { const m = Math.round((Date.now() / 1000 - t) / 60); return m < 1 ? "ahora" : m < 60 ? `hace ${m} min` : `hace ${Math.round(m / 60)} h`; };
      const loadHist = () => fetch("/history").then(r => r.json()).then(d => {
        hist = d.items || [];
        $("#summary-hist").textContent = hist.length;
        const box = $("#hist-list"); box.innerHTML = "";
        hist.slice(0, 8).forEach(h => {
          const c = document.createElement("div");
          c.className = "cell hist-cell";
          c.innerHTML = `<span>${h.lat.toFixed(5)}, ${h.lon.toFixed(5)}</span><span class="val">${ago(h.t)}</span>`;
          c.onclick = () => api().setLatLon(h.lat, h.lon);
          box.appendChild(c);
        });
      }).catch(() => {});
      setInterval(() => { if ($("#hist-sec").open) loadHist(); }, 2500);
      loadHist();
      $("#btn-undo-tp").onclick = () => {
        if (hist.length > 1) { api().setLatLon(hist[1].lat, hist[1].lon); toast("Volviste a la ubicación anterior"); }
        else toast("Aún no hay una ubicación anterior");
      };

      // GPX
      $("#btn-gpx-export").onclick = () => {
        const a = api(), pts = a.getPath().length >= 2 ? a.getPath() : a.getWaypoints();
        if (pts.length < 2) return toast("Marca al menos 2 puntos");
        post("/gpx/save", { points: pts }).then(d => toast(d.ok ? "Guardado en " + d.path : "No se pudo guardar"));
      };
      $("#btn-gpx-import").onclick = () => $("#gpx-file").click();
      $("#gpx-file").onchange = e => {
        const f = e.target.files[0]; if (!f) return;
        f.text().then(x => {
          const doc = new DOMParser().parseFromString(x, "application/xml");
          let pts = [...doc.querySelectorAll("trkpt,rtept,wpt")].map(n => ({ lat: +n.getAttribute("lat"), lon: +n.getAttribute("lon") })).filter(p => isFinite(p.lat) && isFinite(p.lon));
          if (pts.length < 2) return toast("El GPX no tiene puntos válidos");
          const k = Math.ceil(pts.length / 400);
          if (k > 1) pts = pts.filter((_, i) => i % k === 0 || i === pts.length - 1);
          $("#route-streets").checked = false;
          api().setWaypoints(pts);
          api().map.fitBounds(pts.map(p => [p.lat, p.lon]));
          toast(`GPX importado: ${pts.length} puntos`);
        });
        e.target.value = "";
      };

      // Joystick en pantalla (mantener presionado repite)
      document.querySelectorAll(".dpad .btn").forEach(b => {
        let t;
        const fire = () => document.dispatchEvent(new KeyboardEvent("keydown", { key: b.dataset.k }));
        b.addEventListener("pointerdown", () => { fire(); t = setInterval(fire, 110); });
        ["pointerup", "pointerleave", "pointercancel"].forEach(ev => b.addEventListener(ev, () => clearInterval(t)));
      });
    })();
  </script>
<script>
    (() => {
      const $ = s => document.querySelector(s);
      const { toast, post } = window.__ui, api = () => window.__api;
      let lang = "es";

      // Parada en cada punto
      const dw = $("#route-dwell"), dv = $("#dwell-val");
      const syncDw = () => { dv.textContent = dw.value + " s"; dw.style.setProperty("--p", (dw.value / dw.max * 100) + "%"); };
      dw.addEventListener("input", syncDw); syncDw();
      dw.addEventListener("pointerup", () => dw.blur());

      // Favoritos: exportar / importar
      $("#btn-fav-export").onclick = () => post("/favorites/export").then(d => toast(d.ok ? "Guardado en " + d.path : "No se pudo guardar"));
      $("#btn-fav-import").onclick = () => $("#fav-file").click();
      $("#fav-file").onchange = e => {
        const f = e.target.files[0]; if (!f) return;
        f.text().then(x => post("/favorites/import", { favorites: JSON.parse(x) }))
          .then(d => { api().reloadFavorites(); toast("Favoritos importados: " + d.added); })
          .catch(() => toast("Archivo inválido"));
        e.target.value = "";
      };

      // Comandos de atajos globales + rumbo
      const CARD = { es: ["N", "NE", "E", "SE", "S", "SO", "O", "NO"], en: ["N", "NE", "E", "SE", "S", "SW", "W", "NW"] };
      let lastHdg = "";
      const drawHdg = d => {
        const h = d.heading || 0;
        const html = `<span class="arr" style="transform:rotate(${h}deg)">↑</span><span>${CARD[lang][Math.round(h / 45) % 8]} ${Math.round(h)}°</span>` + (d.dwell > 0 ? `<span class="val">${lang === "en" ? "Stop" : "Parada"} ${d.dwell} s</span>` : "");
        if (html !== lastHdg) { lastHdg = html; $("#hdg").innerHTML = html; }
      };
      let lastCmd = {};
      setInterval(() => fetch("/cmds").then(r => r.json()).then(d => {
        lastCmd = d; drawHdg(d);
        (d.cmds || []).forEach(c => {
          if (c === "pause") $("#btn-route-pause").click();
          else if (c === "restore") $("#btn-restore").click();
          else document.dispatchEvent(new KeyboardEvent("keydown", { key: c }));
        });
      }).catch(() => {}), 300);

      // ---------- Idioma ES / EN ----------
      const EN = {"Idioma":"Language","Simulador GPS":"GPS Simulator","Ayuda":"Help","Ocultar":"Hide","Dirección o lat, lon":"Address or lat, lon","Ir":"Go","Detenido":"Stopped","Iniciar":"Start","Detener":"Stop","Restaurar ubicación real":"Restore real location","Mapa":"Map","Satélite":"Satellite","Transporte y ruta":"Transport & route","Caminata":"Walk","Bici":"Bike","Carro":"Car","Marcar puntos":"Add points","Marcando...":"Adding...","Deshacer":"Undo","Limpiar":"Clear","Iniciar ruta":"Start route","Pausar":"Pause","Reanudar":"Resume","Importar GPX":"Import GPX","Exportar GPX":"Export GPX","Velocidad":"Speed","Velocidad en km/h":"Speed in km/h","Calles":"Streets","Variación":"Variation","Bucle":"Loop","Parada en cada punto":"Stop at each point","Parada en segundos":"Stop time in seconds","Favoritos":"Favorites","Nombre del lugar":"Place name","Carpeta (opcional)":"Folder (optional)","Guardar":"Save","Elegir favorito…":"Choose favorite…","Borrar":"Delete","Importar":"Import","Exportar":"Export","Historial":"History","Volver a la ubicación anterior":"Back to previous location","Controles y atajos":"Controls & shortcuts","1 Lento":"1 Slow","3 Rápido":"3 Fast","Centrar":"Center","Copiar":"Copy","Seguir marcador":"Follow marker","WASD mover · 1/2/3 paso · Espacio pausa":"WASD move · 1/2/3 step · Space pause","Ctrl+Alt+P pausa · Ctrl+Alt+R restaurar · Ctrl+Alt+↑↓←→ mover (global)":"Ctrl+Alt+P pause · Ctrl+Alt+R restore · Ctrl+Alt+↑↓←→ move (global)","Norte":"North","Sur":"South","Oeste":"West","Este":"East","Conecta tu iPhone":"Connect your iPhone","Ejecuta la app como administrador":"Run the app as administrator","Reiniciar":"Restart","Conecta el iPhone por USB y toca":"Connect the iPhone by USB and tap","Confiar":"Trust","Activa el Modo de desarrollador en Ajustes → Privacidad y seguridad":"Turn on Developer Mode in Settings → Privacy & Security","Algunos juegos y apps prohíben alterar la ubicación y pueden suspender cuentas. Úsalo bajo tu responsabilidad.":"Some games and apps forbid altering your location and may suspend accounts. Use at your own risk.","Entendido":"Got it","Conectando...":"Connecting...","Deteniendo...":"Stopping...","GPS Activo en iPhone":"GPS active on iPhone","Buscando iPhone...":"Looking for iPhone...","Montando imagen de desarrollador...":"Mounting developer image...","Iniciando túnel...":"Starting tunnel...","Iniciando túnel interno...":"Starting internal tunnel...","iPhone no detectado. Revisa el cable USB y toca Confiar.":"iPhone not detected. Check the USB cable and tap Trust.","Ubicación real restaurada":"Real location restored","Volviste a la ubicación anterior":"Back at the previous location","Aún no hay una ubicación anterior":"No previous location yet","Marca al menos 2 puntos":"Add at least 2 points","El GPX no tiene puntos válidos":"The GPX has no valid points","No se pudo guardar":"Could not save","Archivo inválido":"Invalid file","No se pudo pedir permisos de administrador":"Could not request administrator rights","ahora":"now"};
      const MODE = { auto: "car", recta: "straight", peatonal: "pedestrian", caminata: "walking", bici: "bike" };
      const RX = [
        [/^(Caminata|Bici|Carro) · ([0-9]+) pts$/, (_, m, n) => `${EN[m]} · ${n} pts`],
        [/^(.*) · (auto|recta|peatonal|caminata|bici)$/, (_, a, m) => `${a} · ${MODE[m]}`],
        [/^Guardado en (.*)$/, (_, p) => "Saved to " + p],
        [/^GPX importado: ([0-9]+) puntos$/, (_, n) => `GPX imported: ${n} points`],
        [/^Favoritos importados: ([0-9]+)$/, (_, n) => `Favorites imported: ${n}`],
        [/^hace ([0-9]+) (min|h)$/, (_, n, u) => `${n} ${u} ago`],
        [/^Error de túnel: (.*)$/, (_, e) => "Tunnel error: " + e]
      ];
      const tr = str => {
        const t = str.trim(); if (!t) return str;
        let o = EN[t];
        if (o === undefined) for (const [re, f] of RX) { const m = t.match(re); if (m) { o = f(...m); break; } }
        return o === undefined ? str : str.replace(t, () => o);
      };
      const orig = new WeakMap(), done = new WeakMap();
      const apply = n => {
        if (lang !== "en" || n.data === done.get(n)) return;
        if (["SCRIPT", "STYLE"].includes(n.parentNode && n.parentNode.nodeName)) return;
        const t = tr(n.data);
        if (t !== n.data) { orig.set(n, n.data); done.set(n, t); n.data = t; }
      };
      const walk = fn => { const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) fn(n); };
      new MutationObserver(ms => {
        if (lang !== "en") return;
        ms.forEach(m => {
          if (m.type === "characterData") apply(m.target);
          else m.addedNodes.forEach(x => { if (x.nodeType === 3) apply(x); else if (x.nodeType === 1) { const w = document.createTreeWalker(x, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) apply(n); } });
        });
      }).observe(document.body, { childList: true, subtree: true, characterData: true });

      function setLang(l) {
        lang = l; lastHdg = "";
        try { localStorage.setItem("lang", l); } catch (_) {}
        document.documentElement.lang = l;
        $("#lang-es").classList.toggle("active", l === "es");
        $("#lang-en").classList.toggle("active", l === "en");
        if (l === "en") walk(apply); else walk(n => { if (orig.has(n)) { n.data = orig.get(n); orig.delete(n); done.delete(n); } });
        document.querySelectorAll("[placeholder],[aria-label]").forEach(el => ["placeholder", "aria-label"].forEach(a => {
          if (!el.hasAttribute(a)) return;
          el.__es = el.__es || {}; if (el.__es[a] === undefined) el.__es[a] = el.getAttribute(a);
          el.setAttribute(a, l === "en" ? tr(el.__es[a]) : el.__es[a]);
        }));
        drawHdg(lastCmd);
      }
      $("#lang-es").onclick = () => setLang("es");
      $("#lang-en").onclick = () => setLang("en");
      let saved = null; try { saved = localStorage.getItem("lang"); } catch (_) {}
      const first = saved || ((navigator.language || "es").startsWith("es") ? "es" : "en");
      if (first === "en") setLang("en");
    })();
  </script>
</body>
</html>
"""

state = {
    "running": False,
    "active": False,
    "status_text": "Detenido",
    "lat": 25.6866,
    "lon": -100.3161,
    "error": None,
    "tunnel_err": None,
    "route_running": False,
    "route_waypoints": [],
    "route_seg_idx": 0,
    "route_speed_kmh": 45.0,
    "route_loop": False,
    "route_jitter": True,
    "favorites": load_favorites(),
}

def distance_meters(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def route_worker():
    tick = 0.25
    elapsed = 0.0
    while True:
        elapsed += tick
        if state["route_running"] and state["running"] and time.time() >= state["dwell_until"]:
            pts = state["route_waypoints"]
            idx = state["route_seg_idx"]
            if len(pts) >= 2 and idx < len(pts) - 1:
                target = pts[idx + 1]
                cur_lat = state["lat"]
                cur_lon = state["lon"]
                dist = distance_meters(cur_lat, cur_lon, target["lat"], target["lon"])
                if dist > 0.5:
                    state["heading"] = bearing(cur_lat, cur_lon, float(target["lat"]), float(target["lon"]))
                factor = 1.0 + (0.14 * math.sin(elapsed * 0.9)) if state.get("route_jitter") else 1.0
                target_v = max(0.5, ((float(state["route_speed_kmh"]) * factor) * 1000.0) / 3600.0)
                v = state.get("cur_v", 0.0)
                v = min(target_v, v + 2.5 * tick) if v < target_v else max(target_v, v - 4.0 * tick)
                if idx == len(pts) - 2 and not state["route_loop"]:
                    v = min(v, max(0.8, math.sqrt(2 * 3.0 * dist)))
                state["cur_v"] = v
                speed_mps = max(0.5, v)
                step_m = speed_mps * tick
                if dist <= step_m or dist < 1e-6:
                    state["lat"] = float(target["lat"])
                    state["lon"] = float(target["lon"])
                    if state["route_dwell"] > 0 and (idx + 1) in state["route_stops"]:
                        state["dwell_until"] = time.time() + state["route_dwell"]
                        state["cur_v"] = 0.0
                    if idx + 1 < len(pts) - 1:
                        state["route_seg_idx"] = idx + 1
                    elif state["route_loop"]:
                        state["route_seg_idx"] = 0
                        state["lat"] = float(pts[0]["lat"])
                        state["lon"] = float(pts[0]["lon"])
                    else:
                        state["route_running"] = False
                else:
                    ratio = step_m / dist
                    state["lat"] = cur_lat + (float(target["lat"]) - cur_lat) * ratio
                    state["lon"] = cur_lon + (float(target["lon"]) - cur_lon) * ratio
            else:
                state["route_running"] = False
        time.sleep(tick)

def _load_dvt_tools():
    dvt_cls = None
    loc_cls = None
    mounter_fn = None
    try:
        from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import DvtSecureSocketProxyService
        dvt_cls = DvtSecureSocketProxyService
    except Exception:
        pass
    try:
        from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
        loc_cls = LocationSimulation
    except Exception:
        pass
    try:
        from pymobiledevice3.services.mobile_image_mounter import auto_mount
        mounter_fn = auto_mount
    except Exception:
        pass
    if not (dvt_cls and loc_cls and mounter_fn):
        for _, modname, _ in pkgutil.walk_packages(pmd3_services.__path__, pmd3_services.__name__ + "."):
            if any(k in modname for k in ("dvt", "mounter", "location")):
                try:
                    mod = importlib.import_module(modname)
                    if dvt_cls is None:
                        dvt_cls = getattr(mod, "DvtSecureSocketProxyService", None) or getattr(mod, "DvtProvider", None)
                    if loc_cls is None:
                        loc_cls = getattr(mod, "LocationSimulation", None)
                    if mounter_fn is None:
                        mounter_fn = getattr(mod, "auto_mount", None)
                except Exception:
                    pass
    return dvt_cls, loc_cls, mounter_fn

def start_tunnel_daemon():
    from pymobiledevice3.__main__ import main as pmd3_main
    sys.argv = ["pymobiledevice3", "remote", "tunneld", "--port", "49155"]
    try:
        pmd3_main()
    except (Exception, SystemExit) as e:
        state["tunnel_err"] = str(e)

def get_tunnel_rsd():
    resp = requests.get("http://127.0.0.1:49155/", timeout=3)
    data = resp.json()
    for udid, info in data.items():
        if isinstance(info, list) and len(info) > 0:
            info = info[0]
        if isinstance(info, dict) and info.get("tunnel-address") and info.get("tunnel-port"):
            return info["tunnel-address"], int(info["tunnel-port"])
    return None, None

async def _maybe_await(val):
    if inspect.isawaitable(val):
        return await val
    return val

async def _open_obj(obj):
    if hasattr(obj, "__aenter__"):
        res = await obj.__aenter__()
        return res if res is not None else obj
    if hasattr(obj, "connect"):
        await _maybe_await(obj.connect())
        return obj
    if hasattr(obj, "__enter__"):
        res = obj.__enter__()
        return res if res is not None else obj
    return obj

async def _close_obj(obj):
    if obj is None:
        return
    try:
        if hasattr(obj, "__aexit__"):
            await obj.__aexit__(None, None, None)
        elif hasattr(obj, "close"):
            await _maybe_await(obj.close())
        elif hasattr(obj, "__exit__"):
            obj.__exit__(None, None, None)
    except Exception:
        pass

async def _run_dvt_session(addr, port):
    dvt_cls, loc_cls, mounter_fn = _load_dvt_tools()
    if not dvt_cls or not loc_cls:
        raise RuntimeError("No se encontró el módulo DVT en pymobiledevice3.")
    rsd = await _open_obj(RemoteServiceDiscoveryService((addr, port)))
    dvt = None
    sim = None
    try:
        try:
            dvt = await _open_obj(dvt_cls(rsd))
        except Exception:
            if mounter_fn is not None:
                state["status_text"] = "Montando imagen de desarrollador..."
                await _maybe_await(mounter_fn(rsd))
            dvt = await _open_obj(dvt_cls(rsd))
        sim = await _open_obj(loc_cls(dvt))
        set_fn = getattr(sim, "set", None) or getattr(sim, "simulate_location", None)
        while state["running"]:
            await _maybe_await(set_fn(state["lat"], state["lon"]))
            state["active"] = True
            state["status_text"] = "GPS Activo en iPhone"
            state["error"] = None
            await asyncio.sleep(0.5)
        clear_fn = getattr(sim, "clear", None) or getattr(sim, "stop", None)
        if clear_fn is not None:
            await _maybe_await(clear_fn())
    finally:
        await _close_obj(sim)
        await _close_obj(dvt)
        await _close_obj(rsd)
        state["active"] = False
        if not state["running"]:
            state["status_text"] = "Detenido"

def location_loop():
    while True:
        if state["running"]:
            try:
                addr, port = get_tunnel_rsd()
                if addr and port:
                    asyncio.run(_run_dvt_session(addr, port))
                else:
                    state["active"] = False
                    state["status_text"] = "Buscando iPhone..."
                    state["error"] = "iPhone no detectado. Revisa el cable USB y toca Confiar."
            except requests.exceptions.ConnectionError:
                state["active"] = False
                state["status_text"] = "Iniciando túnel..."
                state["error"] = ("Error de túnel: " + state["tunnel_err"]) if state["tunnel_err"] else "Iniciando túnel interno..."
            except Exception as e:
                state["active"] = False
                state["status_text"] = "Error"
                msg = str(e)
                if "DeveloperMode" in msg or "InvalidService" in msg:
                    msg += " (Activa Modo de desarrollador en iPhone > Configuración > Privacidad y seguridad)"
                state["error"] = msg
        time.sleep(1)

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
ROUTES_DIR = os.path.join(BASE_DIR, "rutas")
HISTORY_FILE = os.path.join(BASE_DIR, "historial.json")

def tile_urls():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            key = (json.load(f).get("maptiler_key") or "").strip()
    except Exception:
        key = ""
    if key:
        return (f"https://api.maptiler.com/maps/streets-v2/256/{{z}}/{{x}}/{{y}}.png?key={key}",
                f"https://api.maptiler.com/tiles/satellite-v2/{{z}}/{{x}}/{{y}}.jpg?key={key}")
    return ("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}")

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return True

ADMIN = is_admin()
state["device"] = False
try:
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        state["history"] = json.load(f)[:20]
except Exception:
    state["history"] = []

def push_history(lat, lon):
    h = state["history"]
    if h and distance_meters(h[0]["lat"], h[0]["lon"], lat, lon) < 25:
        return
    h.insert(0, {"lat": lat, "lon": lon, "t": int(time.time())})
    del h[20:]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(h, f)
    except Exception:
        pass

def device_watch():
    while True:
        try:
            addr, port = get_tunnel_rsd()
            state["device"] = bool(addr and port)
        except Exception:
            state["device"] = False
        time.sleep(2)

_geo_cache = {}
_geo_lock = threading.Lock()
_geo_last = [0.0]

def nominatim(q, limit):
    key = (q.lower(), limit)
    if key in _geo_cache:
        return _geo_cache[key]
    with _geo_lock:
        wait = 1.1 - (time.time() - _geo_last[0])
        if wait > 0:
            time.sleep(wait)
        resp = requests.get("https://nominatim.openstreetmap.org/search",
                            params={"q": q, "format": "json", "limit": limit},
                            headers={"User-Agent": "Simulador-GPS/1.1"}, timeout=6)
        _geo_last[0] = time.time()
    items = resp.json()
    if len(_geo_cache) > 300:
        _geo_cache.clear()
    _geo_cache[key] = items
    return items

def parse_map_link(text):
    url = text
    host = re.sub(r"^https?://([^/]+).*", r"\1", text).lower()
    if not any(h in host for h in ("google.", "goo.gl", "apple.com")):
        return None
    try:
        url = requests.get(text, timeout=6, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}).url
    except Exception:
        pass
    for pat in (r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", r"@(-?\d+\.\d+),(-?\d+\.\d+)",
                r"[?&](?:ll|q|center|sll|daddr|destination)=(-?\d+\.\d+)(?:,|%2C)(-?\d+\.\d+)"):
        m = re.search(pat, url)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None

@app.route("/")
def index():
    m, sat = tile_urls()
    return render_template_string(HTML_PAGE, tiles_map=m, tiles_sat=sat)

@app.route("/status")
def status():
    return jsonify({
        "running": state["running"],
        "active": state["active"],
        "status_text": state["status_text"],
        "lat": state["lat"],
        "lon": state["lon"],
        "error": state["error"],
        "route_running": state["route_running"],
        "device": state["device"],
        "admin": ADMIN,
    })

@app.route("/start", methods=["POST"])
def start():
    data = request.get_json(silent=True) or {}
    if "lat" in data and "lon" in data:
        state["lat"] = float(data["lat"])
        state["lon"] = float(data["lon"])
    state["running"] = True
    state["status_text"] = "Conectando..."
    return jsonify({"ok": True})

@app.route("/stop", methods=["POST"])
def stop():
    state["running"] = False
    state["route_running"] = False
    state["status_text"] = "Deteniendo..."
    return jsonify({"ok": True})

@app.route("/cleanup", methods=["POST"])
def cleanup():
    state["running"] = False
    state["route_running"] = False
    state["active"] = False
    state["status_text"] = "Detenido"
    return jsonify({"ok": True})

@app.route("/move", methods=["POST"])
def move():
    data = request.get_json(silent=True) or {}
    if "lat" in data and "lon" in data:
        nl, ng = float(data["lat"]), float(data["lon"])
        if distance_meters(state["lat"], state["lon"], nl, ng) > 1:
            state["heading"] = bearing(state["lat"], state["lon"], nl, ng)
        state["lat"], state["lon"] = nl, ng
        if not state["route_running"]:
            push_history(state["lat"], state["lon"])
    return jsonify({"ok": True})

@app.route("/suggest")
def suggest_places():
    q = (request.args.get("q") or "").strip()
    if len(q) < 3:
        return jsonify({"results": []})
    try:
        raw = nominatim(q, 5)
        results = []
        for item in raw:
            results.append({
                "label": item.get("display_name", ""),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
            })
        return jsonify({"results": results})
    except Exception:
        return jsonify({"results": []})

@app.route("/search", methods=["POST"])
def search_place():
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    if not q:
        return jsonify({"ok": False})
    ll = parse_map_link(q) if re.match(r"https?://", q) else None
    if ll:
        state["lat"], state["lon"] = ll
        return jsonify({"ok": True, "lat": ll[0], "lon": ll[1]})
    if "," in q:
        parts = [p.strip() for p in q.split(",")]
        if len(parts) == 2:
            try:
                rlat = float(parts[0])
                rlon = float(parts[1])
                state["lat"] = rlat
                state["lon"] = rlon
                return jsonify({"ok": True, "lat": rlat, "lon": rlon})
            except ValueError:
                pass
    try:
        items = nominatim(q, 1)
        if items:
            rlat = float(items[0]["lat"])
            rlon = float(items[0]["lon"])
            state["lat"] = rlat
            state["lon"] = rlon
            return jsonify({"ok": True, "lat": rlat, "lon": rlon})
    except Exception:
        pass
    return jsonify({"ok": False})

@app.route("/favorites", methods=["GET", "POST"])
def favorites_endpoint():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "Favorito").strip()
        try:
            flat = float(data["lat"])
            flon = float(data["lon"])
            state["favorites"].append({"name": name, "lat": flat, "lon": flon, "folder": (data.get("folder") or "").strip()})
            save_favorites(state["favorites"])
        except Exception:
            pass
    return jsonify({"favorites": state["favorites"]})

@app.route("/favorites/<int:idx>", methods=["DELETE"])
def delete_favorite(idx):
    if 0 <= idx < len(state["favorites"]):
        state["favorites"].pop(idx)
        save_favorites(state["favorites"])
    return jsonify({"favorites": state["favorites"]})

@app.route("/route/start", methods=["POST"])
def route_start():
    data = request.get_json(silent=True) or {}
    pts = data.get("waypoints") or []
    if len(pts) >= 2:
        state["route_waypoints"] = pts
        state["route_seg_idx"] = 0
        state["route_speed_kmh"] = float(data.get("speed_kmh") or 15.0)
        state["route_loop"] = bool(data.get("loop"))
        state["route_jitter"] = bool(data.get("jitter", True))
        state["route_stops"] = {int(i) for i in (data.get("stops") or [])}
        state["route_dwell"] = float(data.get("dwell") or 0)
        state["dwell_until"] = 0.0
        state["lat"] = float(pts[0]["lat"])
        state["lon"] = float(pts[0]["lon"])
        state["route_running"] = True
        state["running"] = True
        state["cur_v"] = 0.0
    return jsonify({"ok": True})

@app.route("/route/resume", methods=["POST"])
def route_resume():
    data = request.get_json(silent=True) or {}
    if len(state["route_waypoints"]) >= 2:
        state["route_speed_kmh"] = float(data.get("speed_kmh") or state["route_speed_kmh"] or 15.0)
        state["route_loop"] = bool(data.get("loop", state["route_loop"]))
        state["route_jitter"] = bool(data.get("jitter", state["route_jitter"]))
        state["route_running"] = True
        state["running"] = True
        state["cur_v"] = 0.0
    return jsonify({"ok": True})

@app.route("/route/pause", methods=["POST"])
def route_pause():
    state["route_running"] = False
    return jsonify({"ok": True})

@app.route("/route/clear", methods=["POST"])
def route_clear():
    state["route_running"] = False
    state["route_waypoints"] = []
    state["route_seg_idx"] = 0
    return jsonify({"ok": True})

def bearing(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

state.update({"cmds": [], "heading": 0.0, "route_stops": set(), "route_dwell": 0.0, "dwell_until": 0.0})

def hotkeys():
    # Atajos globales (Ctrl+Alt+...) con la API de Windows, sin dependencias extra
    try:
        import ctypes.wintypes as wt
        u = ctypes.windll.user32
        keys = {1: (0x50, "pause"), 2: (0x52, "restore"), 3: (0x26, "w"), 4: (0x28, "s"), 5: (0x25, "a"), 6: (0x27, "d")}
        for i, (vk, _) in keys.items():
            u.RegisterHotKey(None, i, 0x0003 | (0x4000 if i < 3 else 0), vk)
        msg = wt.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312 and msg.wParam in keys:
                state["cmds"].append(keys[msg.wParam][1])
    except Exception:
        pass

@app.route("/cmds")
def cmds():
    c, state["cmds"] = state["cmds"], []
    return jsonify({"cmds": c, "heading": state["heading"], "dwell": max(0, round(state["dwell_until"] - time.time()))})

@app.route("/favorites/import", methods=["POST"])
def favorites_import():
    items = (request.get_json(silent=True) or {}).get("favorites") or []
    seen = {(f["name"], f["lat"], f["lon"]) for f in state["favorites"]}
    added = 0
    for it in items:
        try:
            f = {"name": str(it["name"]).strip() or "Favorito", "lat": float(it["lat"]), "lon": float(it["lon"]),
                 "folder": str(it.get("folder") or "").strip()}
        except Exception:
            continue
        k = (f["name"], f["lat"], f["lon"])
        if k not in seen:
            seen.add(k)
            state["favorites"].append(f)
            added += 1
    save_favorites(state["favorites"])
    return jsonify({"favorites": state["favorites"], "added": added})

@app.route("/favorites/export", methods=["POST"])
def favorites_export():
    os.makedirs(ROUTES_DIR, exist_ok=True)
    path = os.path.join(ROUTES_DIR, time.strftime("favoritos_%Y%m%d_%H%M%S.json"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state["favorites"], f, indent=2, ensure_ascii=False)
    return jsonify({"ok": True, "path": path})

@app.route("/history")
def history_list():
    return jsonify({"items": state["history"]})

@app.route("/gpx/save", methods=["POST"])
def gpx_save():
    pts = (request.get_json(silent=True) or {}).get("points") or []
    if len(pts) < 2:
        return jsonify({"ok": False})
    os.makedirs(ROUTES_DIR, exist_ok=True)
    path = os.path.join(ROUTES_DIR, time.strftime("ruta_%Y%m%d_%H%M%S.gpx"))
    body = "".join('<trkpt lat="%.6f" lon="%.6f"/>' % (float(p["lat"]), float(p["lon"])) for p in pts)
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="Simulador GPS" '
                'xmlns="http://www.topografix.com/GPX/1/1"><trk><name>Ruta</name><trkseg>' + body + "</trkseg></trk></gpx>")
    return jsonify({"ok": True, "path": path})

@app.route("/elevate", methods=["POST"])
def elevate():
    try:
        args = "" if getattr(sys, "frozen", False) else '"%s"' % os.path.abspath(__file__)
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
    except Exception:
        return jsonify({"ok": False})
    if rc <= 32:
        return jsonify({"ok": False})
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return jsonify({"ok": True})

def run_flask():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    try:
        threading.Thread(target=start_tunnel_daemon, daemon=True).start()
        threading.Thread(target=location_loop, daemon=True).start()
        threading.Thread(target=route_worker, daemon=True).start()
        threading.Thread(target=device_watch, daemon=True).start()
        threading.Thread(target=hotkeys, daemon=True).start()
        threading.Thread(target=run_flask, daemon=True).start()
        time.sleep(1.5)
        try:
            win = webview.create_window("Simulador GPS", "http://127.0.0.1:5000", width=1180, height=760)
            webview.start()
        except Exception:
            webbrowser.open("http://127.0.0.1:5000")
            while True:
                time.sleep(1)
        finally:
            state["running"] = False
            state["route_running"] = False
            time.sleep(2.0)  # da tiempo a restaurar la ubicación real del iPhone
            state["active"] = False
            state["status_text"] = "Detenido"
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, str(e), "Error Simulador GPS", 16)
