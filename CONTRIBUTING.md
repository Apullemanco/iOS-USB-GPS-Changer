## Cómo contribuir

Las mejoras, correcciones de errores y nuevas funciones son bienvenidas.

### Flujo de trabajo
1. Haz un Fork de este repositorio.
2. Crea una rama para tu cambio (`git checkout -b feature/nueva-funcion`).
3. Instala las dependencias (`pip install -r requirements.txt`) y prueba tus cambios con `python GPS_App.py` y un dispositivo iOS 17+ conectado por USB. Con iOS 17.4 o superior no hacen falta permisos de administrador.
4. Haz Commit de tus cambios y abre un Pull Request describiendo qué agregaste o corregiste.

### Dónde está cada cosa
- `gpsapp/device.py`: conexión con el iPhone (túnel, Modo de desarrollador, imagen de desarrollador).
- `gpsapp/simulator.py`: motor de posición y rutas.
- `gpsapp/server.py`: API local que usa la interfaz.
- `gpsapp/web/`: interfaz (HTML/CSS/JS). Todo texto nuevo va en **español e inglés** en `gpsapp/web/i18n.js`.
- Si algo falla, revisa `app.log` en `%APPDATA%\iOS-GPS-Simulator\`.

### Ideas para colaborar
- Soporte para importar y exportar rutas en formato KML (además de GPX).
- Conexión inalámbrica por Wi-Fi además de USB mediante túnel remoto.
- Modo oscuro adaptable para la interfaz y el mapa.
- Probar y pulir el soporte para macOS y Linux (la app ya funciona desde el código fuente; los atajos globales solo existen en Windows).
- Nuevos idiomas para la interfaz.

---

## Contributing

Improvements, bug fixes, and new features are welcome.

### Workflow
1. Fork this repository.
2. Create a branch for your change (`git checkout -b feature/new-feature`).
3. Install the dependencies (`pip install -r requirements.txt`) and test your changes with `python GPS_App.py` and an iOS 17+ device connected over USB. Administrator rights are not needed on iOS 17.4 or newer.
4. Commit your changes and open a Pull Request describing what you added or fixed.

### Where things live
- `gpsapp/device.py`: iPhone connection (tunnel, Developer Mode, developer disk image).
- `gpsapp/simulator.py`: position and route engine.
- `gpsapp/server.py`: local API used by the interface.
- `gpsapp/web/`: user interface (HTML/CSS/JS). Every new text goes in **both Spanish and English** in `gpsapp/web/i18n.js`.
- If something fails, check `app.log` in `%APPDATA%\iOS-GPS-Simulator\`.

### Ideas to contribute
- Support for importing and exporting routes in KML format (in addition to GPX).
- Wireless Wi-Fi connection alongside USB via remote tunnel.
- Adaptive dark mode for the UI and map tiles.
- Test and polish macOS and Linux support (the app already runs from source; global hotkeys exist only on Windows).
- New interface languages.
