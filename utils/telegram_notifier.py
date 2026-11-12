import json
import os
import uuid
import urllib.error
import urllib.parse
import urllib.request


def _resumen_linea_programada(item):
    clase = item.get("clase", "(sin clase)")
    fecha = item.get("fecha_objetivo", "(sin fecha)")
    hora = item.get("hora_objetivo", "(sin hora)")
    return f"  ✅ {clase}\n     📅 {fecha} | 🕒 {hora}"


def _resumen_linea_fallo(item):
    clase = item.get("clase", "(sin clase)")
    hora = item.get("hora_objetivo", "(sin hora)")
    motivo = item.get("motivo", "sin_motivo")
    detalle = item.get("detalle", "")
    detalle_corto = detalle[:180]
    return f"  ❌ {clase}\n     🕒 {hora} | 🧾 {motivo}\n     ℹ️ {detalle_corto}"


def _estado_icono(estado):
    estado = (estado or "").lower()
    if estado == "exito":
        return "✅"
    if estado == "parcial":
        return "⚠️"
    if estado == "omitido":
        return "⏭️"
    return "❌"


def _duracion_legible(inicio, fin):
    delta = fin - inicio
    total_seg = int(delta.total_seconds())
    minutos, segundos = divmod(total_seg, 60)
    horas, minutos = divmod(minutos, 60)
    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def _obtener_screenshot_error(reporte):
    for fallo in reporte.get("fallos", []):
        screenshot = fallo.get("screenshot")
        if screenshot and os.path.exists(screenshot):
            return screenshot
    return None


def construir_resumen_telegram(reporte, inicio, fin):
    estado = reporte.get("estado", "desconocido").upper()
    estado_icono = _estado_icono(reporte.get("estado", "desconocido"))
    fecha_objetivo = reporte.get("fecha_objetivo", "(sin fecha objetivo)")
    programadas = reporte.get("programadas", [])
    planificadas = reporte.get("planificadas", [])
    fallos = reporte.get("fallos", [])
    total_encontradas = reporte.get("total_encontradas", 0)
    motivo = reporte.get("motivo", "")
    intentos = reporte.get("intentos", 1)

    lineas = [
        "🤖 AUTOMATE-CLASSES",
        "📊 Resumen de ejecución",
        "",
        f"{estado_icono} Estado: {estado}",
        f"🎯 Fecha objetivo: {fecha_objetivo}",
        f"🕐 Inicio: {inicio.strftime('%Y-%m-%d %H:%M:%S')}",
        f"🕓 Fin: {fin.strftime('%Y-%m-%d %H:%M:%S')}",
        f"⏱️ Duración: {_duracion_legible(inicio, fin)}",
        "",
        "📌 Totales",
        f"- Pendientes encontradas: {total_encontradas}",
        f"- Programadas: {len(programadas)}",
        f"- Planificadas (simulación): {len(planificadas)}",
        f"- Fallos: {len(fallos)}",
        f"- Intentos técnicos: {intentos}",
    ]

    if reporte.get("recuperado_tras_reintentos"):
        lineas.extend(["", "🔄 La ejecución se recuperó después de un error técnico temporal."])

    if motivo:
        lineas.extend(["", f"🧠 Motivo principal: {motivo}"])

    if motivo in ("horario_completo_para_dia_objetivo", "horario_completo_para_dias_objetivo"):
        lineas.extend([
            "",
            f"🗓️ Horario completo para {'la' if ',' not in fecha_objetivo else 'las'} fecha{'s' if ',' in fecha_objetivo else ''} objetivo{'s' if ',' in fecha_objetivo else ''}: {fecha_objetivo}",
            "   No se programaron clases nuevas.",
        ])

    if motivo == "sin_clases_programables":
        tipos_bloqueantes = {"quiz", "examen_final"}
        if any(item["tipo"] in tipos_bloqueantes for item in reporte.get("items_especiales", [])):
            lineas.extend(["", "ℹ️ No se matricularon CLASEs: complete primero el quiz o examen pendiente."])
        else:
            lineas.extend(["", "ℹ️ No se matricularon CLASEs: SMART ZONE sigue inactiva."])

    if motivo == "dias_con_clases_programadas":
        lineas.extend(["", "ℹ️ No se matricularon clases en días con franjas ya ocupadas:"])
        for dia in reporte.get("dias_con_clases_programadas", []):
            lineas.append(f"   📅 {dia['fecha']}: {', '.join(dia['horarios'])}")

    horarios_consultados = reporte.get("horarios_consultados", [])
    if horarios_consultados:
        lineas.extend(["", "🗓️ Horarios consultados"])
        for horario in horarios_consultados:
            ocupados = ", ".join(horario.get("ocupados", [])) or "ninguno"
            faltantes = ", ".join(horario.get("faltantes", [])) or "ninguno"
            lineas.extend([
                f"   📅 {horario.get('fecha', '(sin fecha)')}",
                f"      Ocupados: {ocupados}",
                f"      Faltantes: {faltantes}",
            ])

    if programadas:
        lineas.extend(["", "✅ Clases programadas"])
        lineas.extend(_resumen_linea_programada(item) for item in programadas)

    if planificadas:
        lineas.extend(["", "🧪 Plan de simulación (sin confirmar)"])
        for item in planificadas:
            lineas.append(
                f"  • {item.get('clase', '(sin item)')}\n"
                f"     📅 {item.get('fecha_objetivo', '(sin fecha)')} | "
                f"🕒 {item.get('hora_objetivo', '(sin hora)')} | "
                f"📍 {item.get('sede', '(sin sede)')}"
            )

    if fallos:
        lineas.extend(["", "🚨 Fallos detectados"])
        lineas.extend(_resumen_linea_fallo(item) for item in fallos)

    mensaje = "\n".join(lineas)
    if len(mensaje) > 3900:
        mensaje = mensaje[:3900] + "\n... (resumen recortado)"
    return mensaje


def enviar_mensaje_telegram(bot_token, chat_id, mensaje):
    if not bot_token or not chat_id:
        print("Telegram no configurado. Se omite envío de reporte.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": mensaje}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="ignore")
            data = json.loads(body)
            ok = bool(data.get("ok"))
            if not ok:
                print(f"Telegram respondió con error: {body}")
            return ok
    except urllib.error.HTTPError as e:
        print(f"Error HTTP al enviar Telegram: {e.code} - {e.reason}")
    except Exception as e:
        print(f"Error al enviar Telegram: {e}")
    return False


def enviar_foto_telegram(bot_token, chat_id, ruta_foto, caption=""):
    if not bot_token or not chat_id or not ruta_foto or not os.path.exists(ruta_foto):
        return False

    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    with open(ruta_foto, "rb") as f:
        image_bytes = f.read()

    parts = []
    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
    parts.append(f"{chat_id}\r\n".encode("utf-8"))

    if caption:
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
        parts.append(f"{caption[:1024]}\r\n".encode("utf-8"))

    filename = os.path.basename(ruta_foto)
    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(
        f'Content-Disposition: form-data; name="photo"; filename="{filename}"\r\n'.encode("utf-8")
    )
    parts.append(b"Content-Type: image/png\r\n\r\n")
    parts.append(image_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(parts)
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8", errors="ignore"))
            return bool(data.get("ok"))
    except Exception as e:
        print(f"Error al enviar foto por Telegram: {e}")
        return False


def enviar_resumen_telegram(telegram_cfg, reporte, inicio, fin):
    mensaje = construir_resumen_telegram(reporte, inicio, fin)
    screenshot_error = _obtener_screenshot_error(reporte)
    if screenshot_error:
        enviar_foto_telegram(
            telegram_cfg.bot_token,
            telegram_cfg.chat_id,
            screenshot_error,
            caption="🖼️ Evidencia del error detectado",
        )

    screenshot_omitido = reporte.get("screenshot_omitido")
    if (
        reporte.get("estado") == "omitido"
        and screenshot_omitido
        and os.path.exists(screenshot_omitido)
    ):
        enviar_foto_telegram(
            telegram_cfg.bot_token,
            telegram_cfg.chat_id,
            screenshot_omitido,
            caption="🗓️ Evidencia de omisión por calendario",
        )

    enviado = enviar_mensaje_telegram(telegram_cfg.bot_token, telegram_cfg.chat_id, mensaje)

    sent_schedule_paths = set()
    for horario in reporte.get("horarios_consultados", []):
        screenshot = horario.get("screenshot")
        if screenshot and screenshot not in sent_schedule_paths and os.path.exists(screenshot):
            enviar_foto_telegram(
                telegram_cfg.bot_token,
                telegram_cfg.chat_id,
                screenshot,
                caption=f"🗓️ Horario del {horario.get('fecha', 'día objetivo')}",
            )
            sent_schedule_paths.add(screenshot)

    screenshot_horario_final = reporte.get("screenshot_horario_final")
    if (
        screenshot_horario_final
        and screenshot_horario_final not in sent_schedule_paths
        and os.path.exists(screenshot_horario_final)
    ):
        enviar_foto_telegram(
            telegram_cfg.bot_token,
            telegram_cfg.chat_id,
            screenshot_horario_final,
            caption="🗓️ Horario final del día objetivo",
        )

    if enviado:
        print("Reporte enviado a Telegram correctamente.")
    else:
        print("No fue posible enviar el reporte a Telegram.")
