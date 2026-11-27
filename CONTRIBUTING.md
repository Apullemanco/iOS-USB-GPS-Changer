## Cómo contribuir

Las mejoras, correcciones de errores y nuevas funciones son bienvenidas.

### Flujo de trabajo
1. Haz un Fork de este repositorio.
2. Crea una rama para tu cambio (`git checkout -b feature/nueva-funcion`).
3. Prueba tus cambios ejecutando `py GPS_App.py` como administrador en Windows con un dispositivo iOS 17+ conectado por USB.
4. Haz Commit de tus cambios y abre un Pull Request describiendo qué agregaste o corregiste.

### Ideas para colaborar
- Soporte para importar y exportar rutas en formato KML (además de GPX).
- Conexión inalámbrica por Wi-Fi además de USB mediante túnel remoto.
- Modo oscuro adaptable para la interfaz y el mapa.
- Soporte multiplataforma para macOS y Linux (atajos globales y elevación de permisos sin depender de `ctypes.windll`).
