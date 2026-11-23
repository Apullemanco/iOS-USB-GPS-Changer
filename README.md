# iOS USB GPS Simulator

Aplicación de escritorio para Windows que permite simular y mover la ubicación GPS en tiempo real en dispositivos **iPhone y iPad con iOS 17 o superior** mediante conexión por cable USB.

## Descarga directa
1. Ve a la sección **Releases** en la columna derecha de este repositorio.
2. Descarga el archivo **`GPS_Simulador.exe`**.

## Requisitos previos
1. **PC con Windows 10 u 11.**
2. **Drivers USB de Apple:** Tener instalada la aplicación gratuita **Dispositivos Apple** (desde la Microsoft Store) o **iTunes**.
3. **iPhone / iPad con iOS 17 o superior:** Activar el **Modo de desarrollador** en `Configuración > Privacidad y seguridad > Modo de desarrollador`.
4. **Conexión a internet en la PC (solo la primera vez):** Necesaria durante unos segundos al iniciar la simulación para montar la *Developer Disk Image* de esa versión de iOS.

## Como usar
1. Conecta tu iPhone a la PC mediante cable USB, desbloquea la pantalla y toca **Confiar**.
2. Ejecuta **`GPS_Simulador.exe`**.
   - *Nota de Windows:* Si aparece la alerta azul de Windows SmartScreen (*"Windows protegió su PC"*), haz clic en **Más información > Ejecutar de todas formas** y acepta los permisos de **Administrador (Sí)**.
3. Haz clic en cualquier punto del mapa (o arrastra el marcador azul) y presiona **Iniciar Simulación**.
4. Espera unos segundos hasta que el estado cambie a verde (**`GPS Activo en iPhone`**).
5. Mueve tu ubicación haciendo clic en el mapa o usando las teclas **`W`**, **`A`**, **`S`**, **`D`**.
6. Presiona **Detener** para restaurar el GPS real del dispositivo.

## Compilar desde el código fuente
Si deseas modificar el código o compilar tu propio ejecutable:

pip install -r requirements.txt

py -m PyInstaller --noconsole --onefile --uac-admin --recursive-copy-metadata pymobiledevice3 --collect-all pymobiledevice3 --collect-all pytun_pmd3 --collect-all pyimg4 --collect-all qh3 --collect-all uvicorn --collect-all webview --name "GPS_Simulador" GPS_App.py
