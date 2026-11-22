
## Como usar
1. Conecta tu iPhone a la PC mediante cable USB, desbloquea la pantalla y toca **Confiar**.
2. Ejecuta **`GPS_Simulador.exe`**.
   - *Nota de Windows:* Si aparece la alerta azul de Windows SmartScreen (*"Windows protegio su PC"*), haz clic en **Mas informacion** > **Ejecutar de todas formas** y acepta los permisos de **Administrador (Si)**.
3. Haz clic en cualquier punto del mapa (o arrastra el marcador azul) y presiona **Iniciar Simulacion**.
4. Espera unos segundos hasta que el estado cambie a verde (**`GPS Activo en iPhone`**).
5. Mueve tu ubicacion haciendo clic en el mapa o usando las teclas **`W`**, **`A`**, **`S`**, **`D`**.
6. Presiona **Detener** para restaurar el GPS real del dispositivo.

## Compilar desde el codigo fuente
Si deseas modificar el codigo o compilar tu propio ejecutable:

```powershell
pip install -r requirements.txt
py -m PyInstaller --noconsole --onefile --uac-admin --recursive-copy-metadata pymobiledevice3 --collect-all pymobiledevice3 --collect-all pytun_pmd3 --collect-all pyimg4 --collect-all qh3 --collect-all uvicorn --collect-all webview --name "GPS_Simulador" GPS_App.py
cd "$env:USERPROFILE\Downloads\GPS_App"

@'
# iOS USB GPS Simulator

Aplicacion de escritorio para Windows que permite simular y mover la ubicacion GPS en tiempo real en dispositivos iPhone y iPad con iOS 17 o superior mediante conexion por cable USB.

## Descarga directa
1. Ve a la seccion Releases en la columna derecha de este repositorio.
2. Descarga el archivo GPS_Simulador.exe.

## Requisitos previos
1. PC con Windows 10 u 11.
2. Drivers USB de Apple: Tener instalada la aplicacion gratuita Dispositivos Apple (Microsoft Store) o iTunes.
3. iPhone / iPad con iOS 17 o superior con el Modo de desarrollador activo (Configuracion > Privacidad y seguridad > Modo de desarrollador).
4. Conexion a internet en la PC durante la primera conexion para montar la imagen de desarrollador de esa version de iOS.

## Como usar
1. Conecta tu iPhone por cable USB, desbloquea la pantalla y toca Confiar.
2. Ejecuta GPS_Simulador.exe como Administrador (si aparece Windows SmartScreen, selecciona Mas informacion > Ejecutar de todas formas).
3. Haz clic en cualquier punto del mapa o arrastra el marcador azul y presiona Iniciar Simulacion.
4. Espera unos segundos hasta que el estado cambie a verde (GPS Activo en iPhone).
5. Mueve tu ubicacion haciendo clic en el mapa o usando las teclas W, A, S, D.
6. Presiona Detener para restaurar el GPS real del dispositivo.
