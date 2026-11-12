import os
import asyncio
import argparse
from datetime import timedelta
from playwright.async_api import async_playwright

# Importamos nuestras piezas
from utils.credentials import load_smart_credentials, load_telegram_config
from utils.auth import login_generico
from utils.actions import programar_clases_pendientes, tomar_screenshots, validar_horario_dia_objetivo
from utils.calendar_manager import evaluar_programacion_hoy
from utils.navigation import cerrar_anuncio_inicial, iniciar_programacion_clases, navegar_a_programacion, validar_proceso
from utils.telegram_notifier import enviar_resumen_telegram
from utils.timezone import now_colombia
from utils.profile import load_profile
from utils.execution_policy import (
    is_retryable_technical_failure,
    is_within_programming_window,
    target_offsets_for_run,
)


MAX_TECHNICAL_ATTEMPTS = 3
TECHNICAL_RETRY_DELAY_SECONDS = 10 * 60


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


async def workflow_principal(profile_path=None, dry_run=False, scheduled=False, notify=True):
    profile = load_profile(profile_path)
    dias_a_procesar = list(target_offsets_for_run(profile, scheduled))
    inicio_ejecucion = now_colombia()
    telegram_cfg = load_telegram_config() if notify else None

    dias_validos = []
    dias_permitidos = profile.enabled_weekdays()
    for d in dias_a_procesar:
        evaluacion = evaluar_programacion_hoy(
            dias_anticipacion=d,
            dias_permitidos=dias_permitidos,
        )
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
        "planificadas": [],
        "dias_con_clases_programadas": [],
        "screenshot_horario_final": "",
        "screenshot_omitido": "",
    }

    if scheduled and not profile.automation_enabled:
        reporte["estado"] = "omitido"
        reporte["motivo"] = "automatizacion_desactivada"
        return reporte

    if scheduled and not is_within_programming_window(inicio_ejecucion):
        reporte["estado"] = "omitido"
        reporte["motivo"] = "fuera_ventana_programacion"
        reporte["avisos"].append({
            "motivo": "fuera_ventana_programacion",
            "detalle": "Smart solo permite matrículas entre las 06:00 y las 22:00, hora Colombia.",
        })
        return reporte

    try:
        if not dias_validos:
            reporte["estado"] = "omitido"
            evaluacion_cero = evaluar_programacion_hoy(
                dias_anticipacion=dias_a_procesar[0],
                dias_permitidos=dias_permitidos,
            )
            reporte["motivo"] = evaluacion_cero.get("motivo", "sin_dias_validos")
            reporte["screenshot_omitido"] = await crear_evidencia_omitido(
                nombre_archivo="0_omitido_por_calendario",
                titulo="Ejecucion omitida por reglas de calendario",
                detalle=evaluacion_cero.get("detalle", "Ningún día de los procesados es válido para programar."),
            )
            return reporte

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
                return reporte

            if not await navegar_a_programacion(page):
                screenshot = await tomar_screenshots(page, "4_error_navegacion_programacion")
                reporte["estado"] = "error"
                reporte["motivo"] = "no_fue_posible_navegar_a_programacion"
                reporte["fallos"].append({
                    "motivo": "no_fue_posible_navegar_a_programacion",
                    "detalle": "Falló la navegación al módulo principal de programación.",
                    "screenshot": screenshot,
                })
                return reporte

            await tomar_screenshots(page, "4_navegar_programacion_iniciado")

            # --- PASO 4: ITERAR SOBRE DÍAS VÁLIDOS ---
            for idx, dias_anticipacion in enumerate(dias_validos):
                fecha_objetivo = (inicio_ejecucion + timedelta(days=dias_anticipacion)).strftime("%Y-%m-%d")
                print(f"\n--- Procesando día objetivo: {fecha_objetivo} (anticipación={dias_anticipacion}) ---")

                horarios_configurados = profile.slots_for_weekday(
                    (inicio_ejecucion + timedelta(days=dias_anticipacion)).weekday()
                )
                if not horarios_configurados:
                    reporte["avisos"].append({
                        "fecha": fecha_objetivo,
                        "motivo": "sin_horarios_configurados",
                        "detalle": "El perfil no tiene franjas habilitadas para el día objetivo.",
                    })
                    continue

                validacion_horario = await validar_horario_dia_objetivo(
                    page,
                    dias_desde_hoy=dias_anticipacion,
                    horarios_habituales=horarios_configurados,
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
                        f"{fecha_objetivo} ya tiene programación en {', '.join(horarios_ocupados)}."
                    )
                    reporte["dias_con_clases_programadas"].append({
                        "fecha": fecha_objetivo,
                        "horarios": horarios_ocupados,
                    })
                    uses_group_rules = profile.selection_mode == "groups" and bool(profile.group_rules)
                    if profile.partial_occupancy_policy == "skip_entire_day" and not uses_group_rules:
                        print("El perfil indica omitir el día completo ante ocupación parcial.")
                        continue

                if cantidad_a_programar == 0:
                    print(f"No hay franjas faltantes para {fecha_objetivo}. Día completo, saltando.")
                    continue

                # --- ENTRAR A PROGRAMAR CLASES ---
                iniciar_modulo_programacion = await iniciar_programacion_clases(
                    page,
                    study_plan=profile.study_plan,
                )

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
                    dias_desde_hoy=dias_anticipacion,
                    horarios_objetivo=horarios_faltantes,
                    horarios_ocupados=horarios_ocupados,
                    profile=profile,
                    dry_run=dry_run,
                )

                reporte["programadas"].extend(resultado_programacion.get("programadas", []))
                reporte["planificadas"].extend(resultado_programacion.get("planificadas", []))
                reporte["fallos"].extend(resultado_programacion.get("fallos", []))
                reporte["avisos"].extend(resultado_programacion.get("avisos", []))
                reporte["total_encontradas"] += resultado_programacion.get("total_encontradas", 0)

                items_especiales = resultado_programacion.get("items_especiales", [])
                if items_especiales:
                    reporte["items_especiales"].extend(items_especiales)
                    print(
                        f"{len(items_especiales)} grupos de ítems informativos detectados; "
                        "no se programarán automáticamente."
                    )

                # Cerrar popup de programación antes del siguiente día
                await cerrar_anuncio_inicial(page, "#gxp0_cls")

                # Captura final del horario para el último día procesado
                if resultado_programacion.get("programadas") and not dry_run:
                    await tomar_screenshots(page, f"6_clases_programadas_dia_{dias_anticipacion}")
                    if idx == len(dias_validos) - 1:
                        validacion_horario_final = await validar_horario_dia_objetivo(
                            page,
                            dias_desde_hoy=dias_anticipacion,
                            nombre_screenshot=f"7_horario_final_dia_{dias_anticipacion}",
                        )
                        if validacion_horario_final.get("ok"):
                            reporte["screenshot_horario_final"] = validacion_horario_final.get("screenshot", "")

            if dry_run:
                reporte["estado"] = "exito"
                reporte["motivo"] = "simulacion_completada"
            elif reporte["fallos"] and not reporte["programadas"]:
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
        if notify:
            enviar_resumen_telegram(telegram_cfg, reporte, inicio_ejecucion, fin_ejecucion)
    return reporte


def _merge_attempt_reports(reports: list[dict]) -> dict:
    final_report = dict(reports[-1])
    programmed = []
    seen = set()
    for report in reports:
        for item in report.get("programadas", []):
            key = (
                item.get("clase"),
                item.get("fecha_objetivo"),
                item.get("hora_objetivo"),
            )
            if key not in seen:
                seen.add(key)
                programmed.append(item)

    final_report["programadas"] = programmed
    final_report["intentos"] = len(reports)
    final_report["reintentos"] = max(0, len(reports) - 1)
    final_report["errores_tecnicos_previos"] = [
        {
            "intento": index + 1,
            "motivo": report.get("motivo", "error_tecnico"),
        }
        for index, report in enumerate(reports[:-1])
        if is_retryable_technical_failure(report)
    ]
    if len(reports) > 1 and reports[-1].get("estado") == "exito":
        final_report["recuperado_tras_reintentos"] = True
    return final_report


async def workflow_programado_con_reintentos(
    profile_path=None,
    dry_run=False,
    max_attempts=MAX_TECHNICAL_ATTEMPTS,
    retry_delay_seconds=TECHNICAL_RETRY_DELAY_SECONDS,
):
    start = now_colombia()
    telegram_cfg = load_telegram_config()
    reports = []

    for attempt in range(1, max_attempts + 1):
        print(f"Intento técnico {attempt} de {max_attempts}.")
        report = await workflow_principal(
            profile_path=profile_path,
            dry_run=dry_run,
            scheduled=True,
            notify=False,
        )
        reports.append(report)

        if not is_retryable_technical_failure(report) or attempt == max_attempts:
            break

        print(
            f"Error técnico recuperable ({report.get('motivo')}). "
            f"Nuevo intento en {retry_delay_seconds // 60} minutos."
        )
        await asyncio.sleep(retry_delay_seconds)

    final_report = _merge_attempt_reports(reports)
    enviar_resumen_telegram(telegram_cfg, final_report, start, now_colombia())
    return final_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automatización configurable de Smart")
    parser.add_argument("--profile", help="Ruta al perfil JSON de programación")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Construye y muestra el plan sin confirmar programaciones",
    )
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Respeta el interruptor automation_enabled del perfil",
    )
    args = parser.parse_args()
    if args.scheduled:
        final_report = asyncio.run(workflow_programado_con_reintentos(
            profile_path=args.profile,
            dry_run=args.dry_run,
        ))
    else:
        final_report = asyncio.run(workflow_principal(
            profile_path=args.profile,
            dry_run=args.dry_run,
            scheduled=False,
        ))
    if final_report.get("estado") in {"error", "parcial"}:
        raise SystemExit(1)
