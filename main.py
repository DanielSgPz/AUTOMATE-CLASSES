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
    dias_anticipacion = 1
    inicio_ejecucion = now_colombia()
    fecha_objetivo = (inicio_ejecucion + timedelta(days=dias_anticipacion)).strftime("%Y-%m-%d")
    telegram_cfg = load_telegram_config()
    reporte = {
        "estado": "iniciado",
        "motivo": "",
        "fecha_objetivo": fecha_objetivo,
        "programadas": [],
        "fallos": [],
        "total_encontradas": 0,
        "screenshot_horario_final": "",
        "screenshot_omitido": "",
    }

    try:
        evaluacion = evaluar_programacion_hoy(dias_anticipacion=dias_anticipacion)
        if not evaluacion["ok"]:
            reporte["estado"] = "omitido"
            reporte["motivo"] = evaluacion["motivo"]
            reporte["screenshot_omitido"] = await crear_evidencia_omitido(
                nombre_archivo="0_omitido_por_calendario",
                titulo="Ejecucion omitida por reglas de calendario",
                detalle=evaluacion["detalle"],
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

            # --- PASO 4: VALIDAR HORARIO DEL DÍA OBJETIVO ---
            validacion_horario = await validar_horario_dia_objetivo(
                page,
                dias_desde_hoy=dias_anticipacion,
                nombre_screenshot="5_horario_objetivo_antes",
            )

            if not validacion_horario.get("ok"):
                reporte["estado"] = "error"
                reporte["motivo"] = validacion_horario.get("motivo", "error_validar_horario_dia_objetivo")
                reporte["fallos"].append({
                    "motivo": validacion_horario.get("motivo", "error_validar_horario_dia_objetivo"),
                    "detalle": validacion_horario.get("detalle", "Falló la validación del horario del día objetivo."),
                    "screenshot": validacion_horario.get("screenshot"),
                })
                return

            horarios_faltantes = validacion_horario.get("horarios_faltantes", [])
            cantidad_a_programar = validacion_horario.get("cantidad_a_programar", 0)

            if cantidad_a_programar == 0:
                print("No hay franjas faltantes para el día objetivo. No se programarán clases.")
                reporte["estado"] = "exito"
                reporte["motivo"] = "horario_completo_para_dia_objetivo"
                reporte["screenshot_horario_final"] = validacion_horario.get("screenshot", "")
                return

            # --- PASO 5: ENTRAR A PROGRAMAR CLASES ---
            iniciar_modulo_programacion = await iniciar_programacion_clases(page)

            if not iniciar_modulo_programacion:
                print("No se pudo iniciar la programación.")
                screenshot = await tomar_screenshots(page, "5_error_iniciar_modulo_programacion")
                reporte["estado"] = "error"
                reporte["motivo"] = "no_fue_posible_iniciar_modulo_programacion"
                reporte["fallos"].append({
                    "motivo": "no_fue_posible_iniciar_modulo_programacion",
                    "detalle": "Falló la entrada al flujo de programación de clases.",
                    "screenshot": screenshot,
                })
                return

            print("Flujo de programación iniciado correctamente.")
            await tomar_screenshots(page, "5_modulo_seleccion_clase")

            resultado_programacion = await programar_clases_pendientes(
                page,
                cantidad=cantidad_a_programar,
                sede="GUACARI",
                dias_desde_hoy=dias_anticipacion,
                horarios_objetivo=horarios_faltantes,
            )

            reporte["programadas"] = resultado_programacion.get("programadas", [])
            reporte["fallos"] = resultado_programacion.get("fallos", [])
            reporte["total_encontradas"] = resultado_programacion.get("total_encontradas", 0)

            if resultado_programacion.get("ok"):
                reporte["estado"] = "exito"
                reporte["motivo"] = "programacion_completada"
                print("Clases programadas exitosamente.")
                await tomar_screenshots(page, "6_clases_programadas")

                # Cerrar el popup de programación (#gxp0_b) antes de abrir la ventana de Horario.
                # Si sigue abierto, su iframe bloquea el clic en #BUTTON2.
                await cerrar_anuncio_inicial(page, "#gxp0_cls")

                # Captura final del horario ya actualizado para adjuntar al informe.
                validacion_horario_final = await validar_horario_dia_objetivo(
                    page,
                    dias_desde_hoy=dias_anticipacion,
                    nombre_screenshot="7_horario_objetivo_final",
                )
                if validacion_horario_final.get("ok"):
                    reporte["screenshot_horario_final"] = validacion_horario_final.get("screenshot", "")
            elif reporte["programadas"]:
                reporte["estado"] = "parcial"
                reporte["motivo"] = "programacion_parcial"
            else:
                reporte["estado"] = "error"
                reporte["motivo"] = (
                    reporte["fallos"][0]["motivo"] if reporte["fallos"] else "sin_programaciones"
                )
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