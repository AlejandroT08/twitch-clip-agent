# 🤖 Agente Autónomo: Twitch ➔ Higgsfield AI ➔ YouTube Shorts & TikTok

Agente de escucha activa en tiempo real con **optimización extrema de tokens** para canales de Twitch, transformación de clips mediante **Higgsfield AI** y publicación automática en **YouTube Shorts** y **TikTok**.

---

## 📁 Estructura del Proyecto

```text
twitch_clip_agent/
│
├── config.yaml               # Canales monitoreados, intervalos y estilos
├── .env.example              # Plantilla de claves API y credenciales
├── requirements.txt          # Dependencias de Python
│
├── database.py               # Persistencia SQLite y métricas de tokens (clips_history.db)
├── twitch_listener.py        # Escucha activa de clips en vivo y descarga con yt-dlp
├── transcriber.py            # Transcripción local con faster-whisper (0 tokens de pago)
├── optimizer.py              # Agente cognitivo con llamada única estructurada (~250 tokens)
├── higgsfield_service.py     # Integración oficial con el SDK de Higgsfield AI
│
├── publishers/
│   ├── youtube_publisher.py  # Subida automática a YouTube Shorts (API v3)
│   └── tiktok_publisher.py   # Subida automática a TikTok (Playwright / cookies)
│
└── agent.py                  # Bucle principal de orquestación en tiempo real
```

---

## 🛠️ ¿Qué debes hacer por tu parte? (Pasos a Seguir)

Sigue estos 5 pasos para poner en marcha el sistema:

### Paso 1: Instalar Dependencias del Sistema y Python
Asegúrate de tener instalado [Python 3.10+](https://www.python.org/) y [FFmpeg](https://ffmpeg.org/download.html) en tu sistema (agregado al PATH de Windows).

En tu terminal (PowerShell o CMD), navega a la carpeta del proyecto e instala las librerías:
```powershell
cd C:\Users\aleja\.gemini\antigravity\scratch\twitch_clip_agent
pip install -r requirements.txt
playwright install
```

---

### Paso 2: Crear tu archivo `.env`
Copia el archivo `.env.example` y renómbralo a `.env`:
```powershell
cp .env.example .env
```

---

### Paso 3: Obtener tus Credenciales (APIs)

#### 1. Twitch API (Gratis)
1. Ve a [Twitch Developer Console](https://dev.twitch.tv/console/apps).
2. Inicia sesión y haz clic en **Register Your Application**.
3. Ponle un nombre (ej. `ClipAgentBot`), en OAuth Redirect URLs pon `http://localhost:3000` y categoría `Application Integration`.
4. Copia el **Client ID** y genera un nuevo **Client Secret**.
5. Pégalos en tu `.env` (`TWITCH_CLIENT_ID` y `TWITCH_CLIENT_SECRET`).

#### 2. Higgsfield AI API
1. Entra a [Higgsfield API Console](https://open.higgsfield.ai/).
2. Genera tu API Key ID y tu API Key Secret.
3. En tu `.env`, pon:
   ```env
   HF_KEY="tu_key_id:tu_key_secret"
   ```

#### 3. LLM para Optimización de Tokens (Elige uno)
- **Opción recomendada (Casi $0):** Crea una clave en [Google AI Studio](https://aistudio.google.com/) y colócala en `GEMINI_API_KEY`. (Gemini 2.0 Flash cuesta apenas $0.10 por millón de tokens).
- **Opción $0.00 absoluto:** Instala [Ollama](https://ollama.com/), corre `ollama run qwen2.5:7b` en tu PC y cambia en `config.yaml` el proveedor a `ollama`.

#### 4. YouTube Shorts (Opcional si solo quieres probar descarga y Higgsfield primero)
1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un proyecto y activa la **YouTube Data API v3**.
3. Ve a **Credenciales ➔ Crear credenciales ➔ ID de cliente OAuth (Tipo: Aplicación de escritorio)**.
4. Descarga el JSON de credenciales y guárdalo en la carpeta del proyecto con el nombre `client_secret.json`.

#### 5. TikTok (Opcional)
1. Instala la extensión de navegador **Get cookies.txt LOCALLY** en Chrome/Edge.
2. Inicia sesión en tu cuenta de [TikTok](https://www.tiktok.com).
3. Abre la extensión, exporta las cookies y guárdalas como `tiktok_cookies.txt` en la raíz de este proyecto.

---

### Paso 4: Configurar tus Canales en `config.yaml`
Abre `config.yaml` y edita la lista de streamers que deseas vigilar:
```yaml
twitch:
  monitored_channels:
    - "ibai"
    - "auronplay"
    - "elxokas"
  poll_interval_seconds: 30
  only_when_live: true
```

---

### Paso 5: Ejecutar el Agente
Inicia el agente con:
```powershell
python agent.py
```

El agente:
1. Comprobará periódicamente si los canales están transmitiendo.
2. Interceptará inmediatamente cualquier clip nuevo que los espectadores generen en vivo.
3. Lo descargará y transcribirá localmente (0 tokens).
4. El LLM creará el prompt para Higgsfield y los copys de redes en una sola llamada estructurada (~250 tokens).
5. Higgsfield generará el video transformado.
6. Se subirá automáticamente a YouTube Shorts y TikTok.
7. Te imprimirá en consola el total de clips procesados y el dinero gastado en tokens.
