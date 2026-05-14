import json
import urllib.error
import urllib.parse
import urllib.request


def _resumen_linea_programada(item):
    clase = item.get("clase", "(sin clase)")
    fecha = item.get("fecha_objetivo", "(sin fecha)")
    hora = item.get("hora_objetivo", "(sin hora)")
    return f"- OK: {clase} | Fecha: {fecha} | Hora: {hora}"


def _resumen_linea_fallo(item):
    clase = item.get("clase", "(sin clase)")
    hora = item.get("hora_objetivo", "(sin hora)")
    motivo = item.get("motivo", "sin_motivo")
    detalle = item.get("detalle", "")
    detalle_corto = detalle[:180]
    return f"- FAIL: {clase} | Hora: {hora} | Motivo: {motivo} | {detalle_corto}"


def construir_resumen_telegram(reporte, inicio, fin):
    estado = reporte.get("estado", "desconocido").upper()
    fecha_objetivo = reporte.get("fecha_objetivo", "(sin fecha objetivo)")
    programadas = reporte.get("programadas", [])
    fallos = reporte.get("fallos", [])
    total_encontradas = reporte.get("total_encontradas", 0)
    motivo = reporte.get("motivo", "")

    lineas = [
        "AUTOMATE-CLASSES - Resumen de ejecución",
        f"Estado: {estado}",
        f"Inicio: {inicio.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Fin: {fin.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Fecha objetivo: {fecha_objetivo}",
        f"Clases pendientes encontradas: {total_encontradas}",
        f"Clases programadas: {len(programadas)}",
        f"Fallos: {len(fallos)}",
    ]

    if motivo:
        lineas.append(f"Motivo principal: {motivo}")

    if programadas:
        lineas.append("Programadas:")
        lineas.extend(_resumen_linea_programada(item) for item in programadas)

    if fallos:
        lineas.append("Fallos:")
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


def enviar_resumen_telegram(telegram_cfg, reporte, inicio, fin):
    mensaje = construir_resumen_telegram(reporte, inicio, fin)
    enviado = enviar_mensaje_telegram(telegram_cfg.bot_token, telegram_cfg.chat_id, mensaje)
    if enviado:
        print("Reporte enviado a Telegram correctamente.")
    else:
        print("No fue posible enviar el reporte a Telegram.")