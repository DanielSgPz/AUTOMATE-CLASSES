# AUTOMATE-CLASSES

Automatización con Playwright para programar clases en la plataforma Smart con reglas estrictas de fecha/horario, captura de evidencias y reporte final por Telegram, lo hice para mi y por mi, para que no se me olvide matricular las clases, si alguien llega averlo y necesitarlo contacteme.

## Características

- Login automático en Smart.
- Navegación al módulo de programación.
- Filtro de clases pendientes.
- Programación estricta por horario permitido, porque es el que tengo disponible:
  - 18:00 19:30 (primera clase)
  - 19:30 21:00 (segunda clase)
- Horizonte futuro configurable entre 1 y 14 días.
- Captura de screenshots ante errores.
- Resumen final a Telegram (incluye evidencia si hubo error).
- Ejecución local y con GitHub Actions (cron + manual).
- Perfil recurrente para tipos, prioridades, sedes y horarios.
- Simulación segura antes de confirmar programaciones.
- Interfaz web para editar el perfil y consultar pendientes.

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
  item_types.py
  planner.py
  profile.py
  navigation.py
  pending_items.py
config/
  default_profile.json
services/
  discovery_service.py
web/
  index.html
web_app.py
.github/workflows/automation.yml
```

## Requisitos

- Python 3.11+
- Playwright
- Acceso a la plataforma Smart
- Bot de Telegram (opcional pero super recomendado para saber en que clase estoy)

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

La automatización consulta el horario de hoy como referencia y procesa los días futuros
guardados en el perfil. Las reglas se cargan desde `config/default_profile.json` o desde
la variable `PROGRAMMING_PROFILE_JSON` en GitHub Actions.

### Simular sin confirmar

```powershell
python main.py --profile config/default_profile.json --dry-run
```

La simulación inicia sesión, consulta el horario y los pendientes, pero no confirma
ninguna asignación.

## Perfil de programación

El perfil permite configurar por tipo de ítem:

- Activación.
- Plan de estudios visible en Smart (`study_plan`).
- Sede.
- Días permitidos (`0=lunes`, `6=domingo`).
- Franjas preferidas.
- Cantidad máxima por día.
- Prioridad entre tipos.
- Política ante un horario parcialmente ocupado.
- Horizonte de días futuros.
- Reglas independientes por grupo descubierto (`CLASE`, `SMART ZONE`, etc.).

Los tipos soportados son `class`, `smart_zone`, `quiz_unit`, `final_exam` y
`final_exam_preparation`.

`partial_occupancy_policy` acepta:

- `fill_free_slots`: usa las franjas configuradas que continúen libres.
- `skip_entire_day`: omite el día objetivo si alguna franja configurada está ocupada.

## Aplicación web

Instalar las dependencias y ejecutar:

```powershell
uvicorn web_app:app --reload
```

Abrir `http://127.0.0.1:8000`. Desde allí se puede:

- Guardar usuario y contraseña en el Administrador de credenciales de Windows.
- Explorar los planes de estudio disponibles para cada cuenta.
- Consultar y agrupar todos los pendientes reales sin programarlos.
- Programar clases con una regla principal y activar opcionalmente una regla independiente para Smart Zone.
- Elegir sedes reales consultadas directamente desde Smart.
- Configurar visualmente horizonte, días, sede, horas y máximo para clases y Smart Zone.
- Ejecutar una vez al día a las 06:05 (hora Colombia), revisando hoy y mañana.
- Reintentar hasta tres veces, cada diez minutos, únicamente ante errores técnicos temporales.
- Esperar cada refresco AJAX al recorrer pendientes paginados antes de seleccionar una clase.
- Consultar sedes, días y horarios publicados por Smart sin confirmar la asignación.
- Ejecutar una simulación.
- Confirmar una ejecución real.
- Publicar el perfil en GitHub y activar o detener su ejecución automática.

La contraseña no se guarda en el perfil ni en el repositorio. En Windows se almacena
con Credential Manager; `.env` y variables de entorno continúan disponibles como fallback.

Para publicar desde la web configura un token fino de GitHub con permiso de escritura
sobre Actions Variables y el repositorio en formato `propietario/repositorio`. El token
se conserva en el Administrador de credenciales de Windows, nunca en el perfil.

Esto se podria mejorar, pero cuando ud haga su programador lo pone a corerer como quiera. 

## Configurar Telegram

1. En Telegram, se abre `@BotFather`.
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

- `schedule`: una vez al día a las 06:05, hora Colombia.
- La variable de repositorio `PROGRAMMING_PROFILE_JSON` contiene el perfil publicado por la web.
- La ejecución automática revisa hoy y mañana; el perfil decide los días, grupos, sedes y horarios permitidos.
- `workflow_dispatch`: ejecución manual.

### Secrets requeridos en GitHub

Configura en `Settings > Secrets and variables > Actions`:

- `SMART_USERNAME`
- `SMART_PASSWORD`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

La web crea o actualiza automáticamente la variable `PROGRAMMING_PROFILE_JSON`. Para
hacerlo necesita localmente un token de GitHub con acceso de escritura a Actions Variables.

## Flujo de reporte

Al finalizar la ejecución se envía:

- Un resumen con estado, fechas, totales y detalle de fallos/programaciones.
- Si hubo error con screenshot asociado, se envía la imagen como evidencia.
- Si la ejecución se omite por calendario/festivo, también se envía screenshot de evidencia.
- Si la programación fue exitosa, se envía el horario final del día objetivo.

## Seguridad

- No subir el `.env` al repositorio.
- Usar `.env.example` solo como plantilla.
- Las credenciales en GitHub deben ir únicamente en Secrets.

## Notas operativas

- El sistema bloquea la programación fuera de 6:00 a.m. a 10:00 p.m.
- El script detecta popups de restricción y aborta de forma controlada.
- Si no hay match exacto de fecha/hora permitida, no programa para evitar asignaciones inválidas.
- GitHub Actions aplica el perfil publicado por la UI; si la variable no existe usa
  `config/default_profile.json` como respaldo.
