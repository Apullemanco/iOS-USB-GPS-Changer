import asyncio
import ctypes
import importlib
import inspect
import io
import json
import math
import os
import pkgutil
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
  <title>GPS Simulador</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    :root {
      --glass-tint: rgba(215, 224, 235, 0.26);
      --layer-tint: rgba(255, 255, 255, 0.26);
      --control-bg: rgba(255, 255, 255, 0.34);
      --control-hover: rgba(255, 255, 255, 0.52);
      --hairline: rgba(15, 23, 42, 0.09);
      --text-primary: #0f172a;
      --text-secondary: rgba(15, 23, 42, 0.64);
      --blue: #007aff;
      --blue-tint: rgba(0, 122, 255, 0.16);
      --green: #28cd41;
      --red: #ff3b30;
      --red-tint: rgba(255, 59, 48, 0.16);
      --amber: #ff9f0a;
      --font-sf: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: var(--font-sf);
      color: var(--text-primary);
      background: #dce2ea;
      user-select: none;
      overflow: hidden;
      height: 100vh;
      width: 100vw;
      -webkit-font-smoothing: antialiased;
      font-variant-numeric: tabular-nums;
    }

    #map-wrap {
      position: fixed;
      inset: 0;
      width: 100vw;
      height: 100vh;
    }

    #map {
      width: 100%;
      height: 100%;
    }

    #sidebar-shell {
      position: fixed;
      top: 14px;
      left: 14px;
      width: 304px;
      max-height: calc(100vh - 28px);
      z-index: 1000;
      border-radius: 26px;
      transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.22s ease;
    }

    #sidebar-shell.collapsed {
      transform: translateX(calc(-100% - 28px));
      opacity: 0;
      pointer-events: none;
    }

    .lg-lens {
      position: relative;
      width: 100%;
      max-height: calc(100vh - 28px);
      border-radius: 26px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      box-shadow:
        0 20px 48px rgba(15, 23, 42, 0.18),
        0 2px 8px rgba(15, 23, 42, 0.08),
        inset 0 1px 0.5px rgba(255, 255, 255, 0.85),
        inset 0 -1px 0.5px rgba(255, 255, 255, 0.35);
    }

    .lg-optical-base {
      position: absolute;
      inset: 0;
      background: linear-gradient(
        160deg,
        rgba(235, 241, 248, 0.34) 0%,
        rgba(195, 206, 220, 0.24) 55%,
        rgba(175, 188, 204, 0.28) 100%
      );
      backdrop-filter: blur(15px) saturate(215%) brightness(1.04);
      -webkit-backdrop-filter: blur(15px) saturate(215%) brightness(1.04);
      pointer-events: none;
      z-index: 0;
    }

    .lg-edge-refraction {
      position: absolute;
      inset: 0;
      backdrop-filter: url(#lg-lens-filter);
      -webkit-backdrop-filter: url(#lg-lens-filter);
      opacity: 0.72;
      pointer-events: none;
      z-index: 1;
    }

    .lg-specular-rim {
      position: absolute;
      inset: 0;
      border-radius: 26px;
      padding: 1px;
      pointer-events: none;
      background: linear-gradient(
        138deg,
        rgba(255, 255, 255, 0.92) 0%,
        rgba(255, 255, 255, 0.25) 32%,
        rgba(255, 255, 255, 0.08) 68%,
        rgba(255, 255, 255, 0.65) 100%
      );
      -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
      -webkit-mask-composite: xor;
      mask-composite: exclude;
      z-index: 3;
    }

    .lg-specular-glow {
      position: absolute;
      inset: 0;
      border-radius: 26px;
      pointer-events: none;
      z-index: 2;
      transition: background 0.12s ease-out;
    }

    .lg-body {
      position: relative;
      z-index: 4;
      display: flex;
      flex-direction: column;
      max-height: calc(100vh - 28px);
      width: 100%;
    }

    #sidebar-scroll {
      overflow-y: auto;
      padding: 13px;
      display: flex;
      flex-direction: column;
      gap: 9px;
    }

    #sidebar-scroll::-webkit-scrollbar {
      width: 0;
      height: 0;
    }

    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1px 4px;
    }

    .app-title {
      font-size: 15.5px;
      font-weight: 600;
      letter-spacing: -0.024em;
      color: var(--text-primary);
      text-shadow: 0 1px 10px rgba(255, 255, 255, 0.65);
    }

    .pill-close {
      border: none;
      background: var(--control-bg);
      color: var(--text-secondary);
      font-family: var(--font-sf);
      font-size: 11.5px;
      font-weight: 500;
      padding: 4px 10px;
      border-radius: 999px;
      cursor: pointer;
      transition: background 0.15s ease, color 0.15s ease;
    }
    .pill-close:hover {
      background: var(--control-hover);
      color: var(--text-primary);
    }

    .search-pill {
      position: relative;
      display: flex;
      align-items: center;
      background: rgba(255, 255, 255, 0.42);
      border-radius: 999px;
      padding: 0 6px 0 12px;
      height: 33px;
      box-shadow: inset 0 0.5px 0 rgba(255, 255, 255, 0.85);
      transition: background 0.16s ease, box-shadow 0.16s ease;
    }
    .search-pill:focus-within {
      background: rgba(255, 255, 255, 0.78);
      box-shadow: 0 0 0 2.5px rgba(0, 122, 255, 0.25);
    }

    .search-pill input {
      border: none;
      background: transparent;
      flex: 1;
      min-width: 0;
      font-family: var(--font-sf);
      font-size: 12.5px;
      color: var(--text-primary);
      outline: none;
    }
    .search-pill input::placeholder {
      color: var(--text-secondary);
    }

    .search-go {
      border: none;
      background: var(--blue-tint);
      color: var(--blue);
      font-family: var(--font-sf);
      font-size: 11.5px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 999px;
      cursor: pointer;
      transition: background 0.15s ease;
    }
    .search-go:hover {
      background: rgba(0, 122, 255, 0.24);
    }

    #suggest-list {
      position: absolute;
      top: 38px;
      left: 0;
      right: 0;
      max-height: 180px;
      overflow-y: auto;
      background: rgba(248, 250, 252, 0.88);
      backdrop-filter: blur(24px) saturate(190%);
      -webkit-backdrop-filter: blur(24px) saturate(190%);
      border-radius: 16px;
      box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18), inset 0 0.5px 0 rgba(255, 255, 255, 0.9);
      z-index: 2000;
      display: none;
    }

    .suggest-item {
      padding: 8px 12px;
      font-size: 12px;
      color: var(--text-primary);
      cursor: pointer;
      border-bottom: 0.5px solid var(--hairline);
      line-height: 1.3;
    }
    .suggest-item:last-child { border-bottom: none; }
    .suggest-item:hover {
      background: var(--blue-tint);
    }

    .glass-group {
      background: var(--layer-tint);
      border-radius: 18px;
      box-shadow: inset 0 0.5px 0 rgba(255, 255, 255, 0.65);
      overflow: hidden;
    }

    .group-inner {
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .status-line {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      padding: 0 2px;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--amber);
      box-shadow: 0 0 6px rgba(255, 159, 10, 0.65);
    }
    .dot.active {
      background: var(--green);
      box-shadow: 0 0 8px rgba(40, 205, 65, 0.75);
    }

    .coords {
      font-family: "SF Mono", ui-monospace, Menlo, monospace;
      font-size: 11px;
      font-weight: 500;
      color: var(--text-secondary);
      cursor: pointer;
    }
    .coords:hover {
      color: var(--blue);
    }

    .row {
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .row > * { min-width: 0; }
    .grow { flex: 1; }

    .btn-pill {
      border: none;
      border-radius: 999px;
      height: 30px;
      padding: 0 11px;
      font-family: var(--font-sf);
      font-size: 12px;
      font-weight: 600;
      letter-spacing: -0.01em;
      background: var(--control-bg);
      color: var(--text-primary);
      cursor: pointer;
      transition: background 0.14s ease, transform 0.08s ease;
    }
    .btn-pill:hover {
      background: var(--control-hover);
    }
    .btn-pill:active {
      transform: scale(0.97);
    }

    .btn-primary {
      background: var(--blue);
      color: #ffffff;
      box-shadow: 0 2px 8px rgba(0, 122, 255, 0.28);
    }
    .btn-primary:hover {
      background: #006be0;
    }

    .btn-tint-blue {
      background: var(--blue-tint);
      color: var(--blue);
    }
    .btn-tint-blue:hover {
      background: rgba(0, 122, 255, 0.24);
    }

    .btn-tint-red {
      background: var(--red-tint);
      color: var(--red);
    }
    .btn-tint-red:hover {
      background: rgba(255, 59, 48, 0.24);
    }

    .segmented {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      background: rgba(255, 255, 255, 0.24);
      padding: 2.5px;
      border-radius: 999px;
      height: 29px;
    }
    .segmented.two {
      grid-template-columns: repeat(2, 1fr);
    }

    .seg-opt {
      border: none;
      background: transparent;
      border-radius: 999px;
      font-family: var(--font-sf);
      font-size: 11.5px;
      font-weight: 500;
      color: var(--text-secondary);
      cursor: pointer;
      transition: background 0.16s ease, color 0.16s ease, box-shadow 0.16s ease;
    }
    .seg-opt:hover {
      color: var(--text-primary);
    }
    .seg-opt.active {
      background: rgba(255, 255, 255, 0.85);
      color: var(--text-primary);
      font-weight: 600;
      box-shadow: 0 1px 4px rgba(15, 23, 42, 0.12);
    }

    details.section {
      background: var(--layer-tint);
      border-radius: 18px;
      box-shadow: inset 0 0.5px 0 rgba(255, 255, 255, 0.65);
      overflow: hidden;
    }

    details.section summary {
      list-style: none;
      padding: 9px 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 12.5px;
      font-weight: 600;
      letter-spacing: -0.01em;
      cursor: pointer;
    }
    details.section summary::-webkit-details-marker {
      display: none;
    }

    .sec-sub {
      font-size: 11.5px;
      font-weight: 500;
      color: var(--text-secondary);
    }

    .sec-body {
      padding: 0 10px 10px 10px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .field-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 12px;
      font-weight: 500;
      color: var(--text-primary);
      padding: 2px 2px 0 2px;
    }

    .num-input, .text-input, .select-input {
      border: none;
      background: var(--control-bg);
      border-radius: 999px;
      height: 29px;
      padding: 0 11px;
      font-family: var(--font-sf);
      font-size: 12px;
      color: var(--text-primary);
      outline: none;
    }
    .num-input:focus, .text-input:focus, .select-input:focus {
      background: rgba(255, 255, 255, 0.82);
      box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.25);
    }

    .check-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11.5px;
      padding: 0 2px;
    }

    .check {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-weight: 500;
      color: var(--text-primary);
      cursor: pointer;
    }
    .check input {
      accent-color: var(--blue);
      width: 14px;
      height: 14px;
      margin: 0;
      cursor: pointer;
    }

    .caption {
      font-size: 11px;
      color: var(--text-secondary);
      padding: 0 2px;
    }

    #err {
      font-size: 11px;
      font-weight: 500;
      color: var(--red);
      line-height: 1.35;
      padding: 0 2px;
    }
    #err:empty { display: none; }

    #btn-toggle-bar {
      position: fixed;
      top: 14px;
      left: 14px;
      z-index: 900;
      border: none;
      background: rgba(220, 228, 238, 0.34);
      backdrop-filter: blur(18px) saturate(210%);
      -webkit-backdrop-filter: blur(18px) saturate(210%);
      color: var(--text-primary);
      padding: 7px 15px;
      border-radius: 999px;
      font-family: var(--font-sf);
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 10px 26px rgba(15, 23, 42, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.85);
    }

    .leaflet-control-zoom {
      margin-top: 14px !important;
      margin-right: 14px !important;
      border: none !important;
      border-radius: 999px !important;
      overflow: hidden;
      box-shadow: 0 6px 20px rgba(15, 23, 42, 0.14) !important;
    }
    .leaflet-control-zoom a {
      background: rgba(245, 248, 252, 0.72) !important;
      backdrop-filter: blur(16px) saturate(190%);
      color: var(--text-primary) !important;
      border-bottom: 0.5px solid var(--hairline) !important;
    }
  </style>
</head>
<body>
  <div id="map-wrap">
    <div id="map"></div>
  </div>

  <button id="btn-toggle-bar" type="button" style="display: none;">GPS Simulador</button>

  <aside id="sidebar-shell">
    <svg id="lg-svg" style="position: absolute; width: 304px; height: 600px; pointer-events: none;" aria-hidden="true">
      <defs>
        <filter id="lg-lens-filter" x="-20%" y="-20%" width="140%" height="140%" colorInterpolationFilters="sRGB">
          <feImage id="lg-feimage" x="0" y="0" width="100%" height="100%" result="DISP_MAP" preserveAspectRatio="xMidYMid slice" />
          <feDisplacementMap in="SourceGraphic" in2="DISP_MAP" scale="28" xChannelSelector="R" yChannelSelector="G" result="REFRACTED" />
        </filter>
      </defs>
    </svg>

    <div class="lg-lens">
      <span class="lg-optical-base"></span>
      <span class="lg-edge-refraction" id="lg-refraction"></span>
      <span class="lg-specular-glow" id="lg-specular-glow"></span>
      <span class="lg-specular-rim" id="lg-specular-rim"></span>

      <div class="lg-body">
        <div id="sidebar-scroll">
          <div class="header">
            <span class="app-title">GPS Simulador</span>
            <button id="btn-hide-bar" class="pill-close" type="button">Ocultar</button>
          </div>

          <div class="search-pill">
            <input id="search-input" type="text" placeholder="Buscar lugar o coordenadas" autocomplete="off" />
            <button id="btn-search" class="search-go" type="button">Ir</button>
            <div id="suggest-list"></div>
          </div>

          <div class="glass-group">
            <div class="group-inner">
              <div class="status-line">
                <div class="status-pill">
                  <span id="status-dot" class="dot"></span>
                  <span id="status-badge">Detenido</span>
                </div>
                <span id="coords" class="coords">25.686600, -100.316100</span>
              </div>

              <div class="row">
                <button id="btn-start" class="btn-pill btn-primary grow" type="button">Iniciar</button>
                <button id="btn-stop" class="btn-pill btn-tint-red grow" type="button">Detener</button>
              </div>

              <div class="segmented two">
                <button id="btn-layer-map" class="seg-opt active" type="button">Mapa</button>
                <button id="btn-layer-sat" class="seg-opt" type="button">Satelite</button>
              </div>

              <div id="err"></div>
            </div>
          </div>

          <details class="section" open>
            <summary>
              <span>Ruta</span>
              <span id="route-info" class="sec-sub">Carro · 0 pts</span>
            </summary>
            <div class="sec-body">
              <div class="segmented">
                <button id="btn-mode-walk" class="seg-opt" type="button">Caminata</button>
                <button id="btn-mode-bike" class="seg-opt" type="button">Bici</button>
                <button id="btn-mode-car" class="seg-opt active" type="button">Carro</button>
              </div>

              <div class="row">
                <button id="btn-route-mode" class="btn-pill btn-tint-blue grow" type="button">Marcar puntos</button>
                <button id="btn-route-undo" class="btn-pill" type="button">Deshacer</button>
                <button id="btn-route-clear" class="btn-pill" type="button">Limpiar</button>
              </div>

              <div class="row">
                <button id="btn-route-run" class="btn-pill btn-primary grow" type="button">Iniciar ruta</button>
                <button id="btn-route-pause" class="btn-pill grow" type="button">Pausar</button>
              </div>

              <div class="field-row">
                <span>Velocidad (km/h)</span>
                <input id="route-speed" class="num-input" type="number" min="1" max="250" value="45" style="width: 66px; text-align: right;" />
              </div>

              <div class="check-row">
                <label class="check"><input id="route-streets" type="checkbox" checked /> Calles</label>
                <label class="check"><input id="route-jitter" type="checkbox" checked /> Variacion</label>
                <label class="check"><input id="route-loop" type="checkbox" /> Bucle</label>
              </div>

              <div id="route-stats" class="caption">0 m · ~0 min · auto</div>
            </div>
          </details>

          <details class="section">
            <summary>
              <span>Favoritos</span>
              <span id="summary-favs" class="sec-sub">0</span>
            </summary>
            <div class="sec-body">
              <div class="row">
                <input id="fav-name" class="text-input grow" type="text" placeholder="Nombre del lugar" />
                <button id="btn-fav-save" class="btn-pill btn-tint-blue" type="button">Guardar</button>
              </div>
              <div class="row">
                <select id="fav-select" class="select-input grow">
                  <option value="">Elegir favorito...</option>
                </select>
                <button id="btn-fav-go" class="btn-pill" type="button">Ir</button>
                <button id="btn-fav-del" class="btn-pill btn-tint-red" type="button">Borrar</button>
              </div>
            </div>
          </details>

          <details class="section">
            <summary>
              <span>Controles</span>
              <span id="summary-step" class="sec-sub">Normal</span>
            </summary>
            <div class="sec-body">
              <div class="segmented">
                <button id="btn-step-1" class="seg-opt" type="button">Lento</button>
                <button id="btn-step-2" class="seg-opt active" type="button">Normal</button>
                <button id="btn-step-3" class="seg-opt" type="button">Rapido</button>
              </div>
              <div class="row">
                <button id="btn-center" class="btn-pill grow" type="button">Centrar</button>
                <button id="btn-copy" class="btn-pill grow" type="button">Copiar</button>
                <label class="check"><input id="follow-marker" type="checkbox" /> Seguir</label>
              </div>
              <div class="caption">WASD mover · 1/2/3 paso · Espacio pausa</div>
            </div>
          </details>
        </div>
      </div>
    </div>
  </aside>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    function buildPeripheralLensMap(width, height) {
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(64, Math.round(width));
      canvas.height = Math.max(64, Math.round(height));
      const ctx = canvas.getContext("2d");
      const img = ctx.createImageData(canvas.width, canvas.height);
      const data = img.data;
      const w = canvas.width;
      const h = canvas.height;
      const rimWidth = 22;

      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const distLeft = x;
          const distRight = w - 1 - x;
          const distTop = y;
          const distBottom = h - 1 - y;
          const minEdge = Math.min(distLeft, distRight, distTop, distBottom);

          let dx = 0;
          let dy = 0;
          if (minEdge < rimWidth) {
            const t = 1 - minEdge / rimWidth;
            const bend = t * t * (3 - 2 * t);
            const nx = (x - w * 0.5) / (w * 0.5);
            const ny = (y - h * 0.5) / (h * 0.5);
            dx = -nx * bend;
            dy = -ny * bend;
          }

          const idx = (y * w + x) * 4;
          data[idx] = Math.round((dx * 0.5 + 0.5) * 255);
          data[idx + 1] = Math.round((dy * 0.5 + 0.5) * 255);
          data[idx + 2] = 128;
          data[idx + 3] = 255;
        }
      }

      ctx.putImageData(img, 0, 0);
      return canvas.toDataURL();
    }

    function initLiquidGlassLens() {
      const shell = document.getElementById("sidebar-shell");
      const svg = document.getElementById("lg-svg");
      const feImg = document.getElementById("lg-feimage");
      const refraction = document.getElementById("lg-refraction");
      const rim = document.getElementById("lg-specular-rim");
      const glow = document.getElementById("lg-specular-glow");

      if (navigator.userAgent.toLowerCase().includes("firefox")) {
        refraction.style.display = "none";
      }

      function refreshLens() {
        const rect = shell.getBoundingClientRect();
        const w = Math.max(100, Math.round(rect.width));
        const h = Math.max(100, Math.round(rect.height));
        svg.style.width = `${w}px`;
        svg.style.height = `${h}px`;
        const url = buildPeripheralLensMap(w, h);
        feImg.setAttribute("href", url);
        feImg.setAttributeNS("http://www.w3.org/1999/xlink", "href", url);
      }

      document.addEventListener("mousemove", (e) => {
        const rect = shell.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const ox = Math.max(-1, Math.min(1, (e.clientX - cx) / 420));
        const oy = Math.max(-1, Math.min(1, (e.clientY - cy) / 420));
        const angle = 138 + ox * 26;

        rim.style.background = `linear-gradient(${angle}deg, rgba(255,255,255,0.92) 0%, rgba(255,255,255,0.22) 34%, rgba(255,255,255,0.06) 68%, rgba(255,255,255,0.68) 100%)`;
        glow.style.background = `radial-gradient(circle at ${50 + ox * 24}% ${35 + oy * 24}%, rgba(255,255,255,0.24) 0%, rgba(255,255,255,0) 65%)`;
      });

      window.addEventListener("resize", refreshLens);
      refreshLens();
    }

    document.addEventListener("DOMContentLoaded", () => {
      initLiquidGlassLens();

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
        1: { value: 0.00008, label: "Lento" },
        2: { value: 0.0002,  label: "Normal" },
        3: { value: 0.0005,  label: "Rapido" }
      };

      if (typeof L === "undefined") {
        document.getElementById("err").textContent = "Error al cargar Leaflet.";
        return;
      }

      const osmLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19
      });
      const satLayer = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19 }
      );
      const satLabelsLayer = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19 }
      );

      const map = L.map("map", { layers: [osmLayer], zoomControl: false }).setView([lat, lon], 15);
      L.control.zoom({ position: "topright" }).addTo(map);
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
        sel.innerHTML = '<option value="">Elegir favorito...</option>';
        favorites.forEach((f, i) => {
          const opt = document.createElement("option");
          opt.value = String(i);
          opt.textContent = f.name;
          sel.appendChild(opt);
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
        if (q.length < 2) {
          hideSuggestions();
          return;
        }
        suggestTimer = setTimeout(() => {
          fetch(`/suggest?q=${encodeURIComponent(q)}`)
            .then(r => r.json())
            .then(d => renderSuggestions(d.results || []))
            .catch(() => hideSuggestions());
        }, 300);
      });

      document.getElementById("search-input").addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          document.getElementById("btn-search").click();
        }
      });

      document.addEventListener("click", (e) => {
        if (!e.target.closest(".search-pill")) {
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
          body: JSON.stringify({ name, lat, lon })
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
        btn.classList.toggle("btn-tint-blue", !addingWaypoints);
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
        btn.classList.add("btn-tint-blue");
        btn.textContent = "Marcar puntos";
        const pts = await buildPathFromWaypoints();
        const speedKmh = parseFloat(document.getElementById("route-speed").value) || 15;
        const loop = document.getElementById("route-loop").checked;
        const jitter = document.getElementById("route-jitter").checked;
        fetch("/route/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ waypoints: pts, speed_kmh: speedKmh, loop, jitter })
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
        if state["route_running"] and state["running"]:
            pts = state["route_waypoints"]
            idx = state["route_seg_idx"]
            if len(pts) >= 2 and idx < len(pts) - 1:
                target = pts[idx + 1]
                cur_lat = state["lat"]
                cur_lon = state["lon"]
                dist = distance_meters(cur_lat, cur_lon, target["lat"], target["lon"])
                factor = 1.0 + (0.14 * math.sin(elapsed * 0.9)) if state.get("route_jitter") else 1.0
                speed_mps = max(0.5, ((float(state["route_speed_kmh"]) * factor) * 1000.0) / 3600.0)
                step_m = speed_mps * tick
                if dist <= step_m or dist < 1e-6:
                    state["lat"] = float(target["lat"])
                    state["lon"] = float(target["lon"])
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
        raise RuntimeError("No se encontro el modulo DVT en pymobiledevice3.")
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
                state["status_text"] = "Iniciando tunel..."
                state["error"] = ("Error de tunel: " + state["tunnel_err"]) if state["tunnel_err"] else "Iniciando tunel interno..."
            except Exception as e:
                state["active"] = False
                state["status_text"] = "Error"
                msg = str(e)
                if "DeveloperMode" in msg or "InvalidService" in msg:
                    msg += " (Activa Modo de desarrollador en iPhone > Configuracion > Privacidad y seguridad)"
                state["error"] = msg
        time.sleep(1)

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

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
        state["lat"] = float(data["lat"])
        state["lon"] = float(data["lon"])
    return jsonify({"ok": True})

@app.route("/suggest")
def suggest_places():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 5},
            headers={"User-Agent": "GPS-Simulador/1.0"},
            timeout=5,
        )
        raw = resp.json()
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
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 1},
            headers={"User-Agent": "GPS-Simulador/1.0"},
            timeout=6,
        )
        items = resp.json()
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
            state["favorites"].append({"name": name, "lat": flat, "lon": flon})
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
        state["lat"] = float(pts[0]["lat"])
        state["lon"] = float(pts[0]["lon"])
        state["route_running"] = True
        state["running"] = True
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

def run_flask():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    try:
        threading.Thread(target=start_tunnel_daemon, daemon=True).start()
        threading.Thread(target=location_loop, daemon=True).start()
        threading.Thread(target=route_worker, daemon=True).start()
        threading.Thread(target=run_flask, daemon=True).start()
        time.sleep(1.5)
        try:
            win = webview.create_window("GPS Simulador", "http://127.0.0.1:5000", width=1180, height=760)
            webview.start()
        except Exception:
            webbrowser.open("http://127.0.0.1:5000")
            while True:
                time.sleep(1)
        finally:
            state["running"] = False
            state["route_running"] = False
            state["active"] = False
            state["status_text"] = "Detenido"
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, str(e), "Error GPS Simulador", 16)
