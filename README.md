# iOS USB GPS Simulator

Aplicación de escritorio para Windows que permite simular y mover la ubicación GPS en tiempo real en dispositivos **iPhone y iPad con iOS 17 o superior** mediante conexión por cable USB, con interfaz en **Español** e **English** visible directamente desde la barra lateral.

## Descarga directa
1. Ve a la sección **Releases** en la columna derecha de este repositorio.
2. Descarga el archivo **`GPS_Simulador.exe`**.

## Requisitos previos
1. **PC con Windows 10 u 11.**
2. **Drivers USB de Apple:** Tener instalada la aplicación gratuita **Dispositivos Apple** (desde la Microsoft Store) o **iTunes**.
3. **iPhone / iPad con iOS 17 o superior:** Activar el **Modo de desarrollador** en `Configuración > Privacidad y seguridad > Modo de desarrollador`.
4. **Conexión a internet en la PC:** Necesaria la primera vez para montar la *Developer Disk Image* y también para cargar mapas, autocompletado de direcciones o trazado de rutas por calles.

## Cómo usar
1. Conecta tu iPhone a la PC mediante cable USB, desbloquea la pantalla y toca **Confiar**.
2. Ejecuta **`GPS_Simulador.exe`** (o usa la opción de elevar permisos desde el asistente si no lo abriste como administrador).
  - *Nota de Windows:* Si aparece la alerta de Windows SmartScreen, haz clic en **Más información > Ejecutar de todas formas** y acepta los permisos de **Administrador (Sí)**.
3. Selecciona **Español** o **English** en la tarjeta **Idioma** de la barra lateral, busca una dirección/coordenadas o haz clic en el mapa (o arrastra el marcador azul).
4. Presiona **Iniciar** y espera unos segundos hasta que el estado cambie a verde (**`GPS Activo en iPhone`**).
5. Mueve tu ubicación haciendo clic en el mapa, usando la cruceta en pantalla o las teclas **`W`**, **`A`**, **`S`**, **`D`** (con pasos `1`/`2`/`3` y atajos globales `Ctrl+Alt+...`), o arma una ruta con **Marcar puntos** / **Importar GPX** y **Iniciar ruta**.
6. Presiona **Detener** o **Restaurar ubicación real** para volver a la ubicación real del dispositivo.

## Compilar desde el código fuente
Si deseas modificar el código o compilar tu propio ejecutable:

```powershell
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --collect-submodules pymobiledevice3 --name "GPS_Simulador" GPS_App.py
```

---

# iOS USB GPS Simulator (English)

Windows desktop application that lets you simulate and move the real-time GPS location on **iPhone and iPad devices running iOS 17 or later** over a USB cable connection, with an **Español / English** switcher visible directly in the sidebar.

## Direct Download
1. Go to the **Releases** section on the right column of this repository.
2. Download the **`GPS_Simulador.exe`** file.

## Prerequisites
1. **Windows 10 or 11 PC.**
2. **Apple USB Drivers:** Have the free **Apple Devices** app (from the Microsoft Store) or **iTunes** installed.
3. **iPhone / iPad running iOS 17 or later:** Enable **Developer Mode** in `Settings > Privacy & Security > Developer Mode`.
4. **Internet connection on the PC:** Required the first time to mount the *Developer Disk Image*, and also to load map tiles, address autocomplete, or street routing.

## How to Use
1. Connect your iPhone to the PC via USB cable, unlock the screen, and tap **Trust**.
2. Run **`GPS_Simulador.exe`** (or use the elevate option from the wizard if you did not run it as Administrator).
  - *Windows Note:* If Windows SmartScreen appears, click **More info > Run anyway** and accept the **Administrator (Yes)** prompt.
3. Select **Español** or **English** in the **Language** card on the sidebar, search for an address/coordinates, or click anywhere on the map (or drag the blue marker).
4. Click **Start** and wait a few seconds until the status badge turns green (**`GPS active on iPhone`**).
5. Move your location by clicking on the map, using the on-screen D-pad or the **`W`**, **`A`**, **`S`**, **`D`** keys (with `1`/`2`/`3` steps and `Ctrl+Alt+...` global hotkeys), or build a route with **Add points** / **Import GPX** and **Start route**.
6. Click **Stop** or **Restore real location** to return to the device's real GPS location.

## Build from Source
If you want to modify the code or compile your own executable:

```powershell
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --collect-submodules pymobiledevice3 --name "GPS_Simulador" GPS_App.py
```
