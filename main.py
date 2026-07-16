import os
import asyncio
from datetime import timedelta
from playwright.async_api import async_playwright

# Importamos nuestras piezas
from utils.credentials import load_smart_credentials, load_telegram_config
from utils.auth import login_generico
from utils.actions import iniciar_programacion_clases, navegar_a_programacion, programar_clases_pendientes, tomar_screenshots, validar_proceso, cerrar_anuncio_inicial, validar_horario_dia_objetivo
from utils.calendar_manager import evaluar_programacion_hoy
from utils.telegram_notifier import enviar_resumen_telegram
from utils.timezone import now_colombia


async def crear_evidencia_omitido(nombre_archivo, titulo, detalle):
    os.makedirs("screenshots", exist_ok=True)
    path = f"screenshots/{nombre_archivo}.png"

    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() in {"1", "true", "yes", "on"}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        fecha = now_colombia().strftime("%Y-%m-%d %H:%M:%S %Z")

        await page.set_content(
            f"""
            <html>
              <head>
                <meta charset="utf-8" />
                <style>
                  body {{
                    margin: 0;
                    font-family: 'Segoe UI', Tahoma, sans-serif;
                    background: linear-gradient(135deg, #f3f6ff, #dff3ea);
                    color: #172b4d;
                  }}
                  .card {{
                    max-width: 900px;
                    margin: 80px auto;
                    padding: 36px;
                    border-radius: 16px;
                    background: #ffffff;
                    box-shadow: 0 10px 30px rgba(23, 43, 77, 0.15);
                  }}
                  h1 {{
                    margin: 0 0 12px 0; font-size: 30px; }}
                  p {{
                    margin: 0 0 10px 0; font-size: 18px; line-height: 1.4; }}
                  .meta {{
                    margin-top: 20px; font-size: 15px; color: #42526e; }}
                </style>
              </head>
              <body>
                <div class="card">
                  <h1>{titulo}</h1>
                  <p>{detalle}</p>
                  <p class="meta">AUTOMATE-CLASSES | Evidencia de omisión controlada</p>
                  <p class="meta">Generado: {fecha}</p>
                </div>
              </body>
            </html>
            """
        )

        await page.screenshot(path=path, full_page=True)
        await browser.close()

    print(f"Evidencia de omisión guardada: {path}")
    return path


async def workflow_principal():
    dias_a_procesar = [0, 1]
    inicio_ejecucion = now_colombia()
    telegram_cfg = load_telegram_config()

    dias_validos = []
    for d in dias_a_procesar:
        evaluacion = evaluar_programacion_hoy(dias_anticipacion=d)
        if evaluacion["ok"]:
            dias_validos.append(d)

    fechas_objetivo = [
        (inicio_ejecucion + timedelta(days=d)).strftime("%Y-%m-%d")
        for d in dias_validos
    ]
    reporte = {
        "estado": "iniciado",
        "motivo": "",
        "fecha_objetivo": ", ".join(fechas_objetivo) if fechas_objetivo else "(sin fecha)",
        "programadas": [],
        "fallos": [],
        "total_encontradas": 0,
        "items_especiales": [],
        "avisos": [],
        "dias_con_clases_programadas": [],
        "screenshot_horario_final": "",
        "screenshot_omitido": "",
    }

    try:
        if not dias_validos:
            reporte["estado"] = "omitido"
            evaluacion_cero = evaluar_programacion_hoy(dias_anticipacion=0)
            reporte["motivo"] = evaluacion_cero.get("motivo", "sin_dias_validos")
            reporte["screenshot_omitido"] = await crear_evidencia_omitido(
                nombre_archivo="0_omitido_por_calendario",
                titulo="Ejecucion omitida por reglas de calendario",
                detalle=evaluacion_cero.get("detalle", "Ningún día de los procesados es válido para programar."),
            )
            return

        credenciales = load_smart_credentials()
        headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() in {"1", "true", "yes", "on"}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            # --- PASO 1: LOGIN ---
            await login_generico(page, credenciales.url, credenciales.username, credenciales.password)
            await tomar_screenshots(page, "1_despues_del_login")

            # --- PASO 2: CERRAR MODALES ---
            await cerrar_anuncio_inicial(page, "#gxp0_cls")
            await tomar_screenshots(page, "2_dashboard_limpio")

            # --- PASO 3: VALIDAR PROCESO ---
            validate_status = await validar_proceso(page, "#span_vUSUNOMBRE")

            if validate_status:
                print("El sistema está logueado correctamente")
                await tomar_screenshots(page, "3_sistema_ok")
            else:
                print("ALERTA: Algo falló en la carga")
                screenshot = await tomar_screenshots(page, "3_error_de_carga")
                reporte["estado"] = "error"
                reporte["motivo"] = "validacion_login_fallida"
                reporte["fallos"].append({
                    "motivo": "validacion_login_fallida",
                    "detalle": "No se encontró el selector de usuario logueado.",
                    "screenshot": screenshot,
                })
                return

            if not await navegar_a_programacion(page):
                screenshot = await tomar_screenshots(page, "4_error_navegacion_programacion")
                reporte["estado"] = "error"
                reporte["motivo"] = "no_fue_posible_navegar_a_programacion"
                reporte["fallos"].append({
                    "motivo": "no_fue_posible_navegar_a_programacion",
                    "detalle": "Falló la navegación al módulo principal de programación.",
                    "screenshot": screenshot,
                })
                return

            await tomar_screenshots(page, "4_navegar_programacion_iniciado")

            # --- PASO 4: ITERAR SOBRE DÍAS VÁLIDOS ---
            for idx, dias_anticipacion in enumerate(dias_validos):
                fecha_objetivo = (inicio_ejecucion + timedelta(days=dias_anticipacion)).strftime("%Y-%m-%d")
                print(f"\n--- Procesando día objetivo: {fecha_objetivo} (anticipación={dias_anticipacion}) ---")

                validacion_horario = await validar_horario_dia_objetivo(
                    page,
                    dias_desde_hoy=dias_anticipacion,
                    nombre_screenshot=f"5_horario_dia_{dias_anticipacion}_antes",
                )

                if not validacion_horario.get("ok"):
                    print(f"Error validando horario para {fecha_objetivo}: {validacion_horario.get('motivo')}")
                    reporte["fallos"].append({
                        "fecha": fecha_objetivo,
                        "motivo": validacion_horario.get("motivo", "error_validar_horario_dia_objetivo"),
                        "detalle": validacion_horario.get("detalle", "Falló la validación del horario."),
                        "screenshot": validacion_horario.get("screenshot"),
                    })
                    continue

                horarios_faltantes = validacion_horario.get("horarios_faltantes", [])
                cantidad_a_programar = validacion_horario.get("cantidad_a_programar", 0)
                horarios_ocupados = validacion_horario.get("horarios_ocupados", [])

                if horarios_ocupados:
                    print(
                        f"{fecha_objetivo} ya tiene clases en {', '.join(horarios_ocupados)}. "
                        "No se programa parcialmente este día."
                    )
                    reporte["dias_con_clases_programadas"].append({
                        "fecha": fecha_objetivo,
                        "horarios": horarios_ocupados,
                    })
                    continue

                if cantidad_a_programar == 0:
                    print(f"No hay franjas faltantes para {fecha_objetivo}. Día completo, saltando.")
                    continue

                # --- ENTRAR A PROGRAMAR CLASES ---
                iniciar_modulo_programacion = await iniciar_programacion_clases(page)

                if not iniciar_modulo_programacion:
                    print(f"No se pudo iniciar la programación para {fecha_objetivo}.")
                    screenshot = await tomar_screenshots(page, f"5_error_iniciar_modulo_dia_{dias_anticipacion}")
                    reporte["fallos"].append({
                        "fecha": fecha_objetivo,
                        "motivo": "no_fue_posible_iniciar_modulo_programacion",
                        "detalle": "Falló la entrada al flujo de programación de clases.",
                        "screenshot": screenshot,
                    })
                    continue

                print(f"Flujo de programación iniciado para {fecha_objetivo}.")
                await tomar_screenshots(page, f"5_modulo_seleccion_clase_dia_{dias_anticipacion}")

                resultado_programacion = await programar_clases_pendientes(
                    page,
                    cantidad=cantidad_a_programar,
                    sede="GUACARI",
                    dias_desde_hoy=dias_anticipacion,
                    horarios_objetivo=horarios_faltantes,
                )

                reporte["programadas"].extend(resultado_programacion.get("programadas", []))
                reporte["fallos"].extend(resultado_programacion.get("fallos", []))
                reporte["avisos"].extend(resultado_programacion.get("avisos", []))
                reporte["total_encontradas"] += resultado_programacion.get("total_encontradas", 0)

                items_especiales = resultado_programacion.get("items_especiales", [])
                if items_especiales:
                    reporte["items_especiales"].extend(items_especiales)
                    for item in items_especiales:
                        print(f"  [{item['tipo']}] {item['nombre']} — no programable automáticamente")

                # Cerrar popup de programación antes del siguiente día
                await cerrar_anuncio_inicial(page, "#gxp0_cls")

                # Captura final del horario para el último día procesado
                if resultado_programacion.get("programadas"):
                    await tomar_screenshots(page, f"6_clases_programadas_dia_{dias_anticipacion}")
                    if idx == len(dias_validos) - 1:
                        validacion_horario_final = await validar_horario_dia_objetivo(
                            page,
                            dias_desde_hoy=dias_anticipacion,
                            nombre_screenshot=f"7_horario_final_dia_{dias_anticipacion}",
                        )
                        if validacion_horario_final.get("ok"):
                            reporte["screenshot_horario_final"] = validacion_horario_final.get("screenshot", "")

            if reporte["fallos"] and not reporte["programadas"]:
                reporte["estado"] = "error"
                reporte["motivo"] = reporte["fallos"][0]["motivo"]
            elif reporte["fallos"] and reporte["programadas"]:
                reporte["estado"] = "parcial"
                reporte["motivo"] = "programacion_parcial"
            elif not reporte["fallos"] and not reporte["programadas"]:
                reporte["estado"] = "exito"
                reporte["motivo"] = (
                    "sin_clases_programables" if reporte["avisos"]
                    else "dias_con_clases_programadas" if reporte["dias_con_clases_programadas"]
                    else "horario_completo_para_dias_objetivo"
                )
                if dias_validos and not reporte["avisos"] and not reporte["dias_con_clases_programadas"]:
                    ultima_validacion = await validar_horario_dia_objetivo(
                        page,
                        dias_desde_hoy=dias_validos[-1],
                        nombre_screenshot="7_horario_completo",
                    )
                    if ultima_validacion.get("ok"):
                        reporte["screenshot_horario_final"] = ultima_validacion.get("screenshot", "")
            else:
                reporte["estado"] = "exito"
                reporte["motivo"] = "programacion_completada"
    except Exception as e:
        reporte["estado"] = "error"
        reporte["motivo"] = "excepcion_no_controlada"
        screenshot = ""
        try:
            if "page" in locals():
                screenshot = await tomar_screenshots(page, "error_excepcion_no_controlada")
        except Exception:
            screenshot = ""
        reporte["fallos"].append({
            "motivo": "excepcion_no_controlada",
            "detalle": str(e),
            "screenshot": screenshot,
        })
        print(f"Error no controlado en workflow_principal: {e}")
    finally:
        fin_ejecucion = now_colombia()
        enviar_resumen_telegram(telegram_cfg, reporte, inicio_ejecucion, fin_ejecucion)

if __name__ == "__main__":
    asyncio.run(workflow_principal())
