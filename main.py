import os
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

# Importamos nuestras piezas
from utils.credentials import load_smart_credentials, load_telegram_config
from utils.auth import login_generico
from utils.actions import iniciar_programacion_clases, navegar_a_programacion, programar_clases_pendientes, tomar_screenshots, validar_proceso, cerrar_anuncio_inicial
from utils.calendar_manager import debe_programar_hoy
from utils.telegram_notifier import enviar_resumen_telegram


async def workflow_principal():
    dias_anticipacion = 1
    inicio_ejecucion = datetime.now()
    fecha_objetivo = (inicio_ejecucion + timedelta(days=dias_anticipacion)).strftime("%Y-%m-%d")
    telegram_cfg = load_telegram_config()
    reporte = {
        "estado": "iniciado",
        "motivo": "",
        "fecha_objetivo": fecha_objetivo,
        "programadas": [],
        "fallos": [],
        "total_encontradas": 0,
    }

    try:
        if not debe_programar_hoy(dias_anticipacion=dias_anticipacion):
            reporte["estado"] = "omitido"
            reporte["motivo"] = "no_corresponde_programar_por_calendario"
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
                await tomar_screenshots(page, "3_error_de_carga")
                reporte["estado"] = "error"
                reporte["motivo"] = "validacion_login_fallida"
                reporte["fallos"].append({
                    "motivo": "validacion_login_fallida",
                    "detalle": "No se encontró el selector de usuario logueado.",
                })
                return

            if not await navegar_a_programacion(page):
                reporte["estado"] = "error"
                reporte["motivo"] = "no_fue_posible_navegar_a_programacion"
                reporte["fallos"].append({
                    "motivo": "no_fue_posible_navegar_a_programacion",
                    "detalle": "Falló la navegación al módulo principal de programación.",
                })
                return

            await tomar_screenshots(page, "4_navegar_programacion_iniciado")

            iniciar_modulo_programacion = await iniciar_programacion_clases(page)

            if not iniciar_modulo_programacion:
                print("No se pudo iniciar la programación.")
                reporte["estado"] = "error"
                reporte["motivo"] = "no_fue_posible_iniciar_modulo_programacion"
                reporte["fallos"].append({
                    "motivo": "no_fue_posible_iniciar_modulo_programacion",
                    "detalle": "Falló la entrada al flujo de programación de clases.",
                })
                return

            print("Flujo de programación iniciado correctamente.")
            await tomar_screenshots(page, "5_modulo_seleccion_clase")

            resultado_programacion = await programar_clases_pendientes(
                page,
                cantidad=2,
                sede="GUACARI",
                dias_desde_hoy=dias_anticipacion,
            )

            reporte["programadas"] = resultado_programacion.get("programadas", [])
            reporte["fallos"] = resultado_programacion.get("fallos", [])
            reporte["total_encontradas"] = resultado_programacion.get("total_encontradas", 0)

            if resultado_programacion.get("ok"):
                reporte["estado"] = "exito"
                reporte["motivo"] = "programacion_completada"
                print("Clases programadas exitosamente.")
                await tomar_screenshots(page, "6_clases_programadas")
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
        reporte["fallos"].append({
            "motivo": "excepcion_no_controlada",
            "detalle": str(e),
        })
        print(f"Error no controlado en workflow_principal: {e}")
    finally:
        fin_ejecucion = datetime.now()
        enviar_resumen_telegram(telegram_cfg, reporte, inicio_ejecucion, fin_ejecucion)

if __name__ == "__main__":
    asyncio.run(workflow_principal())