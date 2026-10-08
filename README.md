# Amazon Luna (plugin.program.luna)

Add-on de Kodi que **lista el catalogo de Amazon Luna y lanza los juegos** en un navegador a pantalla completa. Al abrir un juego, Kodi se minimiza; al salir, Kodi se restaura. Sin menus intermedios: es un acceso directo.

## Que hace

1. Lee el catalogo de juegos de Luna (HTML ya renderizado, con Chrome/Chromium en modo `--headless --dump-dom`; Luna no tiene API publica).
2. Muestra la lista en Kodi (titulo + caratula) y la guarda en cache local (24 h por defecto).
3. Al elegir un juego: minimiza Kodi, lo abre en el navegador a pantalla completa (modo `app_fullscreen` por defecto) y, al cerrar el navegador, restaura Kodi.

## Requisitos

- Un navegador basado en Chrome/Chromium (nativo o Flatpak).
- Un perfil de navegador dedicado con la sesion de Amazon Luna iniciada (ajuste *Perfil del navegador*).
- Si Kodi es Flatpak: permiso para lanzar en el host (`flatpak-spawn --host`).

## Ajustes principales

- `luna_url`: direccion de Luna (por defecto `https://luna.amazon.com`).
- `scan_urls`: paginas extra a escanear, separadas por `;`.
- `cache_hours`: horas de cache del catalogo.
- `profile_dir`: carpeta del perfil de navegador dedicado.
- `window_mode`: `app_fullscreen` / `kiosk` / `window`.
- `minimize_kodi`: minimizar Kodi mientras se juega.

## Acceso directo en Kodi

Igual que el lanzador de RetroDECK: un favorito apuntando a `plugin://plugin.program.luna/` con el icono del add-on.

```
<favourite name="Amazon Luna" thumb=".../plugin.program.luna/resources/icon.png">ActivateWindow(10025,"plugin://plugin.program.luna/",return)</favourite>
```
