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
    fallos = reporte.get("fallos", [])
    total_encontradas = reporte.get("total_encontradas", 0)
    motivo = reporte.get("motivo", "")

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
        f"- Fallos: {len(fallos)}",
    ]

    if motivo:
        lineas.extend(["", f"🧠 Motivo principal: {motivo}"])

    if programadas:
        lineas.extend(["", "✅ Clases programadas"])
        lineas.extend(_resumen_linea_programada(item) for item in programadas)

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

    enviado = enviar_mensaje_telegram(telegram_cfg.bot_token, telegram_cfg.chat_id, mensaje)
    if enviado:
        print("Reporte enviado a Telegram correctamente.")
    else:
        print("No fue posible enviar el reporte a Telegram.")