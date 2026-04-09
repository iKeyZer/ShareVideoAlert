# Video Share Alert

> [!WARNING]
> Por el momento el programa funciona unicamente con el chat abierto.
> Proximamente se agregara soporte para activar la alerta mediante puntos del canal, donaciones de Bits y donaciones de dinero.

Overlay para OBS que detecta links de video en el chat de Twitch y los reproduce automáticamente en pantalla. Cuando un espectador pega un link de YouTube, TikTok, Instagram o Twitch Clips en el chat, aparece una alerta con el video reproduciéndose.

---

## Plataformas soportadas

| Plataforma | Formato | Reproducción |
|---|---|---|
| YouTube | 16:9 | iframe embed |
| YouTube Shorts | 9:16 | iframe embed |
| Twitch Clips | 16:9 | iframe embed |
| TikTok | 9:16 | descarga directa via yt-dlp |
| Instagram Reels | 9:16 | descarga directa via yt-dlp |

---

## Requisitos

- Python 3.10 o superior
- Las siguientes librerías (se instalan automáticamente):
  - `yt-dlp`
  - `pillow` (solo para compilar el exe)
  - `pyinstaller` (solo para compilar el exe)

---

## Uso rapido (con el ejecutable)

1. Ejecutar `VideoShareAlert.exe`
2. Escribir el nombre del canal de Twitch
3. Ajustar la duración de la alerta en segundos
4. Hacer clic en **Guardar**
5. Copiar la URL que aparece en pantalla
6. En OBS: Fuentes → + → Fuente de navegador → pegar la URL
7. Configurar el tamaño de la fuente en **600 × 820 px**
8. Posicionar la fuente donde se quiera en la escena

La alerta aparecerá automáticamente cuando alguien pegue un link compatible en el chat.

---

## Uso sin ejecutable (modo desarrollador)

### Opción A — Aplicación con interfaz gráfica

```bash
pip install yt-dlp
python app.py
```

Abre una ventana con la configuración, el estado del servidor y los pasos para OBS.

### Opción B — Servidor standalone (sin interfaz)

```bash
pip install yt-dlp
iniciar-servidor.bat
```

Inicia solo el servidor en `http://localhost:8765`. Abrir esa URL en OBS directamente.

---

## Compilar el ejecutable

Para generar `VideoShareAlert.exe` listo para distribuir:

```bash
construir-exe.bat
```

El ejecutable resultante queda en `dist/VideoShareAlert.exe`. No requiere que el streamer tenga Python instalado.

---

## Estructura del proyecto

```
├── app.py                     # Aplicacion principal (GUI + servidor)
├── server.py                  # Servidor standalone sin GUI
├── video-share-alert-v2.html  # Overlay que se carga en OBS
├── construir-exe.bat          # Script para compilar el .exe
├── iniciar-servidor.bat       # Script para iniciar el servidor standalone
└── 19-1.png                   # Icono del programa
```

---

## Como funciona internamente

```
Chat de Twitch
     │
     │  WebSocket IRC (wss://irc-ws.chat.twitch.tv)
     ▼
video-share-alert-v2.html
     │
     │  Detecta links en los mensajes
     ▼
┌────────────────────────────────────────┐
│  YouTube / Twitch Clips                │
│  → iframe embed directo                │
├────────────────────────────────────────┤
│  TikTok / Instagram                    │
│  → POST http://localhost:8765/video-url│
│  → servidor descarga MP4 con yt-dlp   │
│  → <video> reproduce el MP4 local     │
└────────────────────────────────────────┘
```

Los videos se descargan a `temp_video_N.mp4` junto al ejecutable y se eliminan en la siguiente descarga.

---

## Configuracion

La configuracion se guarda en `config.json` al hacer clic en Guardar:

```json
{
  "channel": "nombre_del_canal",
  "duration": "10"
}
```

El canal y la duración también se pueden pasar directamente por URL:

```
http://localhost:8765/video-share-alert-v2.html?channel=mi_canal&duration=15
```

---

## Notas

- La alerta se cierra automaticamente cuando el video termina o cuando se cumple la duracion maxima configurada, lo que ocurra primero.
- Si hay varios links seguidos, se forma una cola y se reproducen en orden.
- El tamaño del cuadro de video se adapta automaticamente segun el formato del contenido (horizontal o vertical).

---

Licenciado por KeyZer
