# iOS USB GPS Simulator

Aplicación de escritorio para Windows que permite simular y mover la ubicación GPS en tiempo real en dispositivos **iPhone y iPad con iOS 17 o superior** mediante conexión por cable USB, con interfaz en **Español** e **English** visible directamente desde la barra lateral.

## Descarga directa

1. Ve a la sección **Releases** en la columna derecha de este repositorio.
2. Descarga el archivo `GPS_Simulador.exe`.

## Requisitos previos

1. **PC con Windows 10 u 11.**
2. **Drivers USB de Apple:** Tener instalada la aplicación gratuita **Dispositivos Apple** (desde la Microsoft Store) o **iTunes**.
3. **iPhone / iPad con iOS 17 o superior:** Activar el **Modo de desarrollador** en `Configuración > Privacidad y seguridad > Modo de desarrollador`.
4. **Conexión a internet en la PC:** Necesaria la primera vez para montar la *Developer Disk Image* y también para cargar mapas, autocompletado de direcciones o trazado de rutas por calles.

## Cómo usar

1. Conecta tu iPhone a la PC mediante cable USB, desbloquea la pantalla y toca **Confiar**.
2. Ejecuta `GPS_Simulador.exe` (o usa la opción de elevar permisos desde el asistente si no lo abriste como administrador).
   * *Nota de Windows:* Si aparece la alerta de Windows SmartScreen, haz clic en **Más información > Ejecutar de todas formas** y acepta los permisos de **Administrador (Sí)**.
3. Selecciona **Español** o **English** en la tarjeta **Idioma** de la barra lateral, busca una dirección/coordenadas o haz clic en el mapa (o arrastra el marcador azul).
4. Presiona **Iniciar** y espera unos segundos hasta que el estado cambie a verde (`GPS Activo en iPhone`).
5. Mueve tu ubicación haciendo clic en el mapa, usando la cruceta en pantalla o las teclas `W`, `A`, `S`, `D` (con pasos `1 / 2 / 3` y atajos globales `Ctrl+Alt+...`), o arma una ruta con **Marcar puntos / Importar GPX** y **Iniciar ruta**.
6. Presiona **Detener** o **Restaurar ubicación real** para volver a la ubicación real del dispositivo.

## Compilar desde el código fuente

Si deseas modificar el código o compilar tu propio ejecutable:

```bash
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --collect-submodules pymobiledevice3 --collect-submodules webview --collect-all flask --hidden-import requests --name "GPS_Simulador" GPS_App.py
