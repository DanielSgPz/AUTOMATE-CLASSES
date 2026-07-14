# AUTOMATE-CLASSES

Automatización con Playwright para programar clases en la plataforma Smart con reglas estrictas de fecha/horario, captura de evidencias y reporte final por Telegram.

## Características

- Login automático en Smart.
- Navegación al módulo de programación.
- Filtro de clases pendientes.
- Programación estricta por horario permitido:
  - 18:00 19:30 (primera clase)
  - 19:30 21:00 (segunda clase)
- Validación por fecha objetivo (mañana por defecto).
- Captura de screenshots ante errores.
- Resumen final a Telegram (incluye evidencia si hubo error).
- Ejecución local y con GitHub Actions (cron + manual).

## Estructura del proyecto

```text
main.py
requirements.txt
utils/
  actions.py
  auth.py
  calendar_manager.py
  credentials.py
  telegram_notifier.py
.github/workflows/automation.yml
```

## Requisitos

- Python 3.11+
- Playwright
- Acceso a la plataforma Smart
- Bot de Telegram (opcional pero recomendado)

## Configuración local

1. Crear y activar entorno virtual.
2. Instalar dependencias:

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

3. Crear archivo `.env` en la raíz del proyecto con este formato:

```env
SMART_LOGIN_URL=https://schoolpack.smart.edu.co/idiomas/alumnos.aspx
SMART_USERNAME=tu_usuario
SMART_PASSWORD=tu_password
PLAYWRIGHT_HEADLESS=false

TELEGRAM_BOT_TOKEN=tu_bot_token
TELEGRAM_CHAT_ID=tu_chat_id
```

4. Ejecutar:

```powershell
python main.py
```

## Configurar Telegram

1. En Telegram, abre `@BotFather`.
2. Ejecuta `/newbot` y crea el bot.
3. Guarda el token entregado por BotFather.
4. Abre chat con tu bot y envía `/start`.
5. Obtén tu chat id en:

```text
https://api.telegram.org/bot<TU_TOKEN>/getUpdates
```

6. Busca `message.chat.id` en la respuesta JSON.

## GitHub Actions

El workflow está en `.github/workflows/automation.yml`.

- `schedule`: 11:00 UTC (6:00 AM Colombia), solo los días previos a clase.
  - Domingo: programa clases del lunes.
  - Lunes: programa clases del martes.
  - Miércoles: programa clases del jueves.
  - Jueves: programa clases del viernes.
- `workflow_dispatch`: ejecución manual.

### Secrets requeridos en GitHub

Configura en `Settings > Secrets and variables > Actions`:

- `SMART_USERNAME`
- `SMART_PASSWORD`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Flujo de reporte

Al finalizar la ejecución se envía:

- Un resumen con estado, fechas, totales y detalle de fallos/programaciones.
- Si hubo error con screenshot asociado, se envía la imagen como evidencia.
- Si la ejecución se omite por calendario/festivo, también se envía screenshot de evidencia.
- Si la programación fue exitosa, se envía el horario final del día objetivo.

## Seguridad

- No subas `.env` al repositorio.
- Usa `.env.example` solo como plantilla.
- Las credenciales en GitHub deben ir únicamente en Secrets.

## Notas operativas

- El sistema puede bloquear programación fuera de 6:00 a.m. a 10:00 p.m.
- El script detecta popups de restricción y aborta de forma controlada.
- Si no hay match exacto de fecha/hora permitida, no programa para evitar asignaciones inválidas.
