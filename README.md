# iOS GPS Simulator · Simulador GPS para iOS

**[English](#english) · [Español](#español)**

---

## English

Free and open-source desktop app to simulate the GPS location of an **iPhone or iPad running iOS 17 or newer** over a USB cable. You can teleport, move with the keyboard, or play back routes at walking, cycling or driving speed. The interface is available in English and Spanish.

### Features

- **Teleport**: click the map, drag the marker, search an address, paste `lat, lon`, or paste a Google Maps / Apple Maps / OpenStreetMap link.
- **Move**: WASD or the arrow keys, an on-screen D-pad, and global hotkeys that work while the window is in the background.
- **Routes**: real street routing for walking, cycling and driving, with realistic acceleration and braking, adjustable speed (changeable while the route plays), natural speed variation, loops, and a pause at each waypoint.
- **GPX import/export**, **favorites** with folders (import/export), and **history**.
- **No administrator rights needed on iOS 17.4+**: the app uses an in-process userspace tunnel.
- A setup assistant that detects common problems: Apple driver missing, *Trust* not accepted, phone locked, Developer Mode off.
- Pressing **Stop** or closing the app always gives the device back its real location.
- **Liquid glass interface**: surfaces bend the map at their edges with chromatic aberration, highlights follow the mouse, and the menu button expands into the panel (and compresses back). On slow computers you can turn the effect off in *Controls & shortcuts*.

### Requirements

| | |
|---|---|
| Computer | Windows 10/11. macOS and Linux work from source. |
| Apple driver (Windows) | **Apple Devices** (Microsoft Store) or iTunes |
| Device | iOS/iPadOS 17 or newer with **Developer Mode** on (*Settings → Privacy & Security → Developer Mode*) |
| Internet | Needed for the map, search, routing, and once per iOS version to download the developer disk image |

> The *Developer Mode* switch only appears in Settings after a developer tool has connected. The app reveals it automatically the first time you press **Start**.

### Download

Get `GPS_Simulador.exe` from the **Releases** page and run it. If Windows SmartScreen appears, choose *More info → Run anyway*.

### Usage

1. Connect the device by USB, unlock it and tap **Trust**.
2. Open the app, pick a place (click, search or paste a link) and press **Start**.
3. When the status turns green (*GPS active on iPhone*), move freely or plan a route:
   *Add points on the map* → click waypoints → *Start route*.
4. Press **Stop** to restore the real location.

| Shortcut | Action |
|---|---|
| `W A S D` / arrow keys | Move one step |
| `1` `2` `3` | Step size 10 / 25 / 60 m |
| `Space` | Pause / resume the route |
| `Ctrl+Alt+P` (global) | Pause / resume the route |
| `Ctrl+Alt+R` (global) | Stop and restore the real location |
| `Ctrl+Alt+arrows` (global) | Move one step |

### Run from source

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python GPS_App.py                 # or: python -m gpsapp
```

On macOS and Linux, devices on iOS 17.0–17.3 need `sudo` because of the privileged tunnel. iOS 17.4 and newer works without it.

### Build the executable

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm GPS_Simulador.spec    # -> dist/GPS_Simulador.exe
```

### Where your data is stored

Favorites, history and settings are saved in a per-user folder, so they survive updates:

- Windows: `%APPDATA%\iOS-GPS-Simulator\`
- macOS: `~/Library/Application Support/iOS-GPS-Simulator/`
- Linux: `~/.config/iOS-GPS-Simulator/`

To keep the data next to the program instead (portable mode), set the environment variable `GPS_SIM_DATA_DIR`. If something goes wrong, check `app.log` in that folder.

**Optional:** for higher-quality map tiles, create `config.json` in that folder containing `{"maptiler_key": "YOUR_KEY"}`. A free key is available from [MapTiler](https://www.maptiler.com/).

### Troubleshooting

| Message | Fix |
|---|---|
| *Apple device service not found* | Install **Apple Devices** from the Microsoft Store, or iTunes |
| *Tap "Trust" on the iPhone* | Unlock the phone and accept the prompt |
| *Turn on Developer Mode* | Settings → Privacy & Security → Developer Mode, then restart the phone |
| *iOS 17.0–17.3 needs administrator rights* | Click **Restart as admin**, or update iOS |
| *Could not prepare the iPhone* | The developer disk image is downloaded once and needs internet |

### Project layout

```
GPS_App.py            launcher
gpsapp/
  main.py             wires everything together, opens the window
  device.py           iPhone connection: tunnel, Developer Mode, disk image, location push
  simulator.py        position and route playback engine (thread-safe)
  server.py           local HTTP API (127.0.0.1, random port, per-session token)
  geo.py              distance and bearing math, search (Photon / Nominatim), map links
  store.py            favorites and history (atomic JSON writes)
  platform_utils.py   admin rights, global hotkeys (Windows)
  paths.py            data folder locations
  web/                user interface (HTML/CSS/JS, Leaflet)
    i18n.js           all interface text, in Spanish and English
    liquid-glass.js   liquid glass effect (vanilla port of liquid-glass-react)
```

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). To add a language, copy the `en` block in `gpsapp/web/i18n.js`.

### License

[MIT](LICENSE). Free to use, modify and share.

### Credits

Built on [pymobiledevice3](https://github.com/doronz88/pymobiledevice3), [Leaflet](https://leafletjs.com/), [pywebview](https://pywebview.flowrl.com/) and [Flask](https://flask.palletsprojects.com/). Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors. Routing by [FOSSGIS OSRM](https://routing.openstreetmap.de/). Search by [Photon](https://photon.komoot.io/) and [Nominatim](https://nominatim.org/). Satellite imagery © Esri. Liquid glass effect ported from [liquid-glass-react](https://github.com/rdev/liquid-glass-react) by Max Rovensky (MIT, see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)).

### Disclaimer

This tool is meant for development, testing and privacy. Many games and apps forbid location spoofing in their terms and may ban accounts. Use it at your own risk.

---

## Español

Aplicación de escritorio gratuita y de código abierto para simular la ubicación GPS de un **iPhone o iPad con iOS 17 o superior** mediante cable USB. Puedes teletransportarte, moverte con el teclado o reproducir rutas a velocidad de caminata, bicicleta o auto. La interfaz está disponible en español e inglés.

### Funciones

- **Teletransporte**: haz clic en el mapa, arrastra el marcador, busca una dirección, pega `lat, lon` o pega un enlace de Google Maps / Apple Maps / OpenStreetMap.
- **Movimiento**: WASD o las flechas, un control direccional en pantalla y atajos globales que funcionan aunque la ventana esté en segundo plano.
- **Rutas**: trazado real por calles para caminata, bici y auto, con aceleración y frenado realistas, velocidad ajustable (se puede cambiar durante la ruta), variación natural de velocidad, bucle y parada en cada punto.
- **Importar/exportar GPX**, **favoritos** con carpetas (importar/exportar) e **historial**.
- **Sin permisos de administrador en iOS 17.4+**: la app usa un túnel propio en espacio de usuario.
- Un asistente de conexión que detecta los problemas comunes: falta el controlador de Apple, no se aceptó *Confiar*, iPhone bloqueado, Modo de desarrollador desactivado.
- Al pulsar **Detener** o cerrar la app, el dispositivo siempre recupera su ubicación real.
- **Interfaz de vidrio líquido**: las superficies refractan el mapa en sus bordes con aberración cromática, los brillos siguen al mouse y el botón del menú se expande para convertirse en el panel (y se comprime de vuelta). En computadoras lentas puedes desactivar el efecto en *Controles y atajos*.

### Requisitos

| | |
|---|---|
| Computadora | Windows 10/11. macOS y Linux funcionan desde el código fuente. |
| Controlador de Apple (Windows) | **Dispositivos Apple** (Microsoft Store) o iTunes |
| Dispositivo | iOS/iPadOS 17 o superior con el **Modo de desarrollador** activo (*Ajustes → Privacidad y seguridad → Modo de desarrollador*) |
| Internet | Necesario para el mapa, la búsqueda, las rutas y, una vez por versión de iOS, para descargar la imagen de desarrollador |

> La opción *Modo de desarrollador* solo aparece en Ajustes después de que una herramienta de desarrollo se conecta. La app la hace aparecer automáticamente la primera vez que pulsas **Iniciar**.

### Descarga

Descarga `GPS_Simulador.exe` desde la sección **Releases** y ejecútalo. Si aparece Windows SmartScreen, elige *Más información → Ejecutar de todas formas*.

### Uso

1. Conecta el dispositivo por USB, desbloquéalo y toca **Confiar**.
2. Abre la app, elige un lugar (clic, búsqueda o enlace) y pulsa **Iniciar**.
3. Cuando el estado se ponga verde (*GPS activo en el iPhone*), muévete libremente o planea una ruta:
   *Marcar puntos en el mapa* → haz clic en los puntos → *Iniciar ruta*.
4. Pulsa **Detener** para restaurar la ubicación real.

| Atajo | Acción |
|---|---|
| `W A S D` / flechas | Moverse un paso |
| `1` `2` `3` | Tamaño de paso 10 / 25 / 60 m |
| `Espacio` | Pausar / reanudar la ruta |
| `Ctrl+Alt+P` (global) | Pausar / reanudar la ruta |
| `Ctrl+Alt+R` (global) | Detener y restaurar la ubicación real |
| `Ctrl+Alt+flechas` (global) | Moverse un paso |

### Ejecutar desde el código fuente

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python GPS_App.py                 # o: python -m gpsapp
```

En macOS y Linux, los dispositivos con iOS 17.0–17.3 requieren `sudo` por el túnel privilegiado. Con iOS 17.4 o superior no hace falta.

### Compilar el ejecutable

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm GPS_Simulador.spec    # -> dist/GPS_Simulador.exe
```

### Dónde se guardan tus datos

Los favoritos, el historial y la configuración se guardan en una carpeta del usuario, así que se conservan al actualizar:

- Windows: `%APPDATA%\iOS-GPS-Simulator\`
- macOS: `~/Library/Application Support/iOS-GPS-Simulator/`
- Linux: `~/.config/iOS-GPS-Simulator/`

Para guardar los datos junto al programa (modo portátil), define la variable de entorno `GPS_SIM_DATA_DIR`. Si algo falla, revisa `app.log` en esa carpeta.

**Opcional:** para mapas de mejor calidad, crea `config.json` en esa carpeta con `{"maptiler_key": "TU_CLAVE"}`. Puedes obtener una clave gratuita en [MapTiler](https://www.maptiler.com/).

### Solución de problemas

| Mensaje | Solución |
|---|---|
| *No se encontró el servicio de dispositivos Apple* | Instala **Dispositivos Apple** desde Microsoft Store, o iTunes |
| *Toca «Confiar» en el iPhone* | Desbloquea el iPhone y acepta el aviso |
| *Activa el Modo de desarrollador* | Ajustes → Privacidad y seguridad → Modo de desarrollador, y reinicia el iPhone |
| *iOS 17.0–17.3 requiere permisos de administrador* | Pulsa **Reiniciar como admin** o actualiza iOS |
| *No se pudo preparar el iPhone* | La imagen de desarrollador se descarga una vez y necesita internet |

### Estructura del proyecto

```
GPS_App.py            lanzador
gpsapp/
  main.py             une todas las piezas y abre la ventana
  device.py           conexión con el iPhone: túnel, Modo de desarrollador, imagen, envío de ubicación
  simulator.py        motor de posición y reproducción de rutas (seguro entre hilos)
  server.py           API HTTP local (127.0.0.1, puerto aleatorio, token por sesión)
  geo.py              cálculo de distancias y rumbos, búsqueda (Photon / Nominatim), enlaces de mapas
  store.py            favoritos e historial (escritura JSON atómica)
  platform_utils.py   permisos de administrador, atajos globales (Windows)
  paths.py            ubicación de la carpeta de datos
  web/                interfaz (HTML/CSS/JS, Leaflet)
    i18n.js           todos los textos de la interfaz, en español e inglés
    liquid-glass.js   efecto de vidrio líquido (adaptación de liquid-glass-react)
```

Las contribuciones son bienvenidas: consulta [CONTRIBUTING.md](CONTRIBUTING.md). Para agregar un idioma, copia el bloque `en` de `gpsapp/web/i18n.js`.

### Licencia

[MIT](LICENSE). Libre para usar, modificar y compartir.

### Créditos

Construido con [pymobiledevice3](https://github.com/doronz88/pymobiledevice3), [Leaflet](https://leafletjs.com/), [pywebview](https://pywebview.flowrl.com/) y [Flask](https://flask.palletsprojects.com/). Datos del mapa © colaboradores de [OpenStreetMap](https://www.openstreetmap.org/copyright). Rutas de [FOSSGIS OSRM](https://routing.openstreetmap.de/). Búsqueda de [Photon](https://photon.komoot.io/) y [Nominatim](https://nominatim.org/). Imágenes satelitales © Esri. Efecto de vidrio líquido adaptado de [liquid-glass-react](https://github.com/rdev/liquid-glass-react) de Max Rovensky (MIT, ver [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)).

### Aviso

Esta herramienta está pensada para desarrollo, pruebas y privacidad. Muchos juegos y apps prohíben falsear la ubicación en sus términos y pueden suspender cuentas. Úsala bajo tu propia responsabilidad.
