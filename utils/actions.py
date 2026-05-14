import os
import re
from datetime import datetime, timedelta

HORARIOS_PERMITIDOS = ["18:00 19:30", "19:30 21:00"]


def _normalizar_texto(texto):
    return re.sub(r"\s+", " ", texto).strip().upper()


def _patrones_fecha_objetivo(dias_desde_hoy=1):
    fecha_objetivo = datetime.now() + timedelta(days=dias_desde_hoy)
    nombres_dia = {
        0: "LUNES",
        1: "MARTES",
        2: "MIERCOLES",
        3: "JUEVES",
        4: "VIERNES",
        5: "SABADO",
        6: "DOMINGO",
    }

    return {
        f"{fecha_objetivo.day:02d}/{fecha_objetivo.month:02d}/{fecha_objetivo.year}",
        f"{fecha_objetivo.day:02d}/{fecha_objetivo.month:02d}",
        f"{fecha_objetivo.day}/{fecha_objetivo.month}/{fecha_objetivo.year}",
        f"{fecha_objetivo.day}/{fecha_objetivo.month}",
        nombres_dia[fecha_objetivo.weekday()],
        nombres_dia[fecha_objetivo.weekday()][:3],
    }


def _fecha_objetivo_iso(dias_desde_hoy=1):
    fecha_objetivo = datetime.now() + timedelta(days=dias_desde_hoy)
    return fecha_objetivo.strftime("%Y-%m-%d")

async def tomar_screenshots(page, nombre_tarea):
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")
    
    path = f"screenshots/{nombre_tarea}.png"
    await page.screenshot(path=path, full_page=True)
    print(f"Evidencia guardada: {path}")
    return path

async def validar_proceso(page, selector):
    # Verifica si un elemento existe para confirmar que todo va bien
    try:
        print(f"Validando presencia de: {selector}")
        await page.wait_for_selector(selector, timeout=5000)
        print(f"Elemento {selector} encontrado.")
        return True
    except:
        return False
    


async def cerrar_anuncio_inicial(page, selector):
    print(f"Buscando elemento para cerrar: {selector}")
    try:
        # Uso locator para tener acceso a métodos de visibilidad
        elemento = page.locator(selector)
        
        # Esperamos a que sea visible
        await elemento.wait_for(state="visible", timeout=5000)
        
        # Pausa de seguridad (humana)
        await page.wait_for_timeout(1000)

        # 2. Intento de clic normal con "force"
        print(f"Intentando clic forzado en {selector}...")
        await elemento.click(force=True)
        print(f"Clic forzado en {selector} realizado.")
        
        # 3. Verificación: ¿Sigue ahí? Si sigue, intentamos vía JavaScript
        await page.wait_for_timeout(1000)
        if await elemento.is_visible():
            print("El clic normal falló, intentando vía JavaScript...")
            await page.evaluate(f"document.querySelector('{selector}').click()")

        print(f"Proceso de cierre para {selector} finalizado.")
        await page.wait_for_timeout(1500) # Tiempo para que el modal desaparezca visualmente
            
    except Exception:
        # No imprimimos el error completo para no ensuciar la consola 
        # si el anuncio simplemente nunca salió.
        print(f"No fue necesario cerrar el elemento {selector}.")
        
        
async def navegar_a_programacion(page):
    """Función base: Nos deja en la pantalla de 'Programación de Clases'."""
    print("Navegando al módulo principal de programación...")
    try:
        # Clic en el icono inicial de Programación (IMAGE18)
        await page.click("#IMAGE18")
        
        # Esperamos a que la pantalla 'Programación de Clases' cargue
        # El texto "Programación de Clases" es un buen indicador
        await page.wait_for_selector("text=Programación de Clases", timeout=10000)
        print("Estamos en el menú de Programación.")
        return True
    except Exception as e:
        print(f"Error al entrar al módulo: {e}")
        return False

async def iniciar_programacion_clases(page):
    """
    Acción específica: Selecciona el plan y da clic en Iniciar.
    """
    print("Ejecutando flujo de: Programar Clases")
    try:
        # Seleccionamos el plan (el span que brilla en cian en tu imagen)
        await page.click("#span_W0030TMPDESART_0001")
        # Clic en el botón rojo 'Iniciar'
        await page.click("#W0030BUTTON1")
        await page.wait_for_load_state("networkidle")
        return True
    except Exception as e:
        print(f"No se pudo iniciar la programación: {e}")
        return False
    
async def programar_clase_especifica(page, nombre_clase):
    """
    Entra al iframe de programación, filtra por pendientes y asigna una clase.
    """
    print(f"Iniciando proceso para programar: {nombre_clase}")
    try:
        # 1. Localizar el iframe del popup
        # GeneXus usa casi siempre este ID para sus popups
        frame = page.frame_locator("#gxp0_ifrm")

        # 2. Seleccionar "Pendientes por programar" en el select
        # El valor "2" corresponde a esa opción según tu HTML
        print("Filtrando por clases pendientes...")
        dropdown = frame.locator("#vTPEAPROBO")
        await dropdown.select_option("2")
        
        # Esperamos a que la tabla se actualice tras el filtro
        await page.wait_for_timeout(2000)

        # 3. Seleccionar la clase específica (ej. CLASE 38)
        # Usamos el texto exacto para ser más flexibles que con el ID dinámico
        print(f"Buscando el texto: {nombre_clase}")
        clase_selector = frame.get_by_text(nombre_clase, exact=True)
        await clase_selector.click()

        # 4. Clic en el botón "Asignar"
        # Usamos el ID BUTTON1 que está DENTRO del frame
        print("Dando clic en el botón Asignar...")
        boton_asignar = frame.locator("#BUTTON1")
        await boton_asignar.dispatch_event("click")
        print("Esperando respuesta del sistema...")
        try:
            # Esperamos a que aparezca el texto del mensaje de restricción horaria
            await page.wait_for_selector("text=sistema de programación está habilitado", timeout=8000)
            print("Mensaje de restricción horaria detectado.")
        except:
            print("No se detectó el mensaje de horario, verificando otros cambios...")

        # Damos un par de segundos para que el screenshot capture el popup abierto
        await page.wait_for_timeout(3000)

    except Exception as e:
        print(f"Error programando la clase en el iframe: {e}")
        return False
    
    
async def programar_clases_pendientes(page, cantidad=2, sede="GUACARI", dias_desde_hoy=1):
    """
    Busca automáticamente las clases pendientes y programa la cantidad solicitada.
    """
    print(f"Buscando las próximas {cantidad} clases disponibles...")
    resultado = {
        "ok": False,
        "fecha_objetivo": _fecha_objetivo_iso(dias_desde_hoy),
        "programadas": [],
        "fallos": [],
        "total_encontradas": 0,
    }
    try:
        if cantidad > len(HORARIOS_PERMITIDOS):
            print(
                f"La cantidad solicitada ({cantidad}) supera los horarios permitidos ({len(HORARIOS_PERMITIDOS)})."
            )
            resultado["fallos"].append({
                "motivo": "cantidad_supera_horarios_permitidos",
                "detalle": f"Solicitadas={cantidad}, Permitidas={len(HORARIOS_PERMITIDOS)}",
            })
            return resultado

        frame = page.frame_locator("#gxp0_ifrm")

        # 1. Filtramos por "Pendientes por programar" (valor 2)
        dropdown = frame.locator("#vTPEAPROBO")
        await dropdown.select_option("2")
        await page.wait_for_timeout(2000) # Esperamos el refresco AJAX

        # 2. Obtenemos todos los elementos que contienen el texto "CLASE"
        # Usamos un selector CSS que busque los spans cuyo ID empiece por span_vPRONOMPRO
        clases_pendientes = frame.locator("span[id^='span_vPRONOMPRO']")
        
        total_encontradas = await clases_pendientes.count()
        resultado["total_encontradas"] = total_encontradas
        print(f"Se encontraron {total_encontradas} clases pendientes.")

        if total_encontradas == 0:
            print("No hay clases para programar hoy.")
            resultado["fallos"].append({
                "motivo": "sin_clases_pendientes",
                "detalle": "No se encontraron clases con el filtro actual.",
            })
            return resultado

        # 3. Iteramos para programar la cantidad deseada (por defecto 2)
        programadas = 0
        for i in range(total_encontradas):
            if programadas >= cantidad:
                break

            clase_actual = clases_pendientes.nth(i)
            nombre_clase = await clase_actual.inner_text()

            if not re.match(r'^CLASE\s+\d+', nombre_clase.strip()):
                print(f"Saltando: {nombre_clase}")
                continue

            print(f"Programando automáticamente: {nombre_clase}")
            await clase_actual.click()
            await frame.locator("#BUTTON1").dispatch_event("click")

            # Esperamos a que aparezca el popup de respuesta del sistema.
            try:
                await page.wait_for_selector("#gxp1_b", state="visible", timeout=7000)
            except Exception:
                print("No apareció ningún popup tras hacer clic en Asignar.")
                screenshot = await tomar_screenshots(page, f"6_sin_popup_clase_{programadas + 1}")
                resultado["fallos"].append({
                    "clase": nombre_clase,
                    "hora_objetivo": HORARIOS_PERMITIDOS[programadas],
                    "motivo": "sin_popup_tras_asignar",
                    "detalle": "No apareció el popup del sistema tras asignar.",
                    "screenshot": screenshot,
                })
                return resultado

            # Distinguimos el tipo de popup por su título (#gxp1_gxtitle):
            # - "Selección de clases" → popup de horario → continuar.
            # - "Mensaje"             → restricción 6am-10pm → detener.
            titulo_popup = (await page.locator("#gxp1_gxtitle").inner_text()).strip()
            print(f"Popup detectado: '{titulo_popup}'")
            if titulo_popup.lower() != "selección de clases":
                print("Popup de restricción horaria. Fuera del horario permitido (6am–10pm).")
                screenshot = await tomar_screenshots(page, "6_fuera_de_horario")
                resultado["fallos"].append({
                    "clase": nombre_clase,
                    "hora_objetivo": HORARIOS_PERMITIDOS[programadas],
                    "motivo": "fuera_de_horario_programacion",
                    "detalle": f"Popup recibido: {titulo_popup}",
                    "screenshot": screenshot,
                })
                return resultado

            horario_objetivo = HORARIOS_PERMITIDOS[programadas]
            print(f"Horario objetivo para esta clase: {horario_objetivo}")
            seleccion = await seleccionar_horario_especifico(
                page,
                sede=sede,
                horario_objetivo=horario_objetivo,
                dias_desde_hoy=dias_desde_hoy,
            )
            if not seleccion["ok"]:
                resultado["fallos"].append({
                    "clase": nombre_clase,
                    "hora_objetivo": horario_objetivo,
                    "motivo": seleccion.get("motivo", "error_seleccion_horario"),
                    "detalle": seleccion.get("detalle", "No fue posible seleccionar el horario."),
                })
                return resultado

            resultado["programadas"].append({
                "clase": nombre_clase,
                "fecha_objetivo": resultado["fecha_objetivo"],
                "hora_objetivo": horario_objetivo,
                "fila_seleccionada": seleccion.get("fila_texto", ""),
            })
            
            programadas += 1
       
        resultado["ok"] = len(resultado["programadas"]) == cantidad
        return resultado

    except Exception as e:
        print(f"Error en la selección automática: {e}")
        resultado["fallos"].append({
            "motivo": "excepcion_programacion",
            "detalle": str(e),
        })
        return resultado
    
    
async def seleccionar_horario_especifico(page, sede="GUACARI", horario_objetivo="18:00 19:30", dias_desde_hoy=1):
    """
    Maneja el popup de segundo nivel (gxp1_ifrm) para confirmar la sede, dia y hora.
    """
    try:
        # Localizamos el iframe del segundo nivel
        # #gxp1_b ya fue confirmado como visible y con iframe por el llamador.
        frame_lvl1 = page.frame_locator("#gxp1_ifrm")

        # 1. Seleccionar la Sede
        print(f"Seleccionando sede: {sede}")
        # Usamos el selector parcial por si el ID de GeneXus cambia el prefijo
        await frame_lvl1.locator("select[id$='vSEDEID']").select_option(label=sede)

        # 2. Seleccionar el día objetivo (mañana) cuando exista el combo de día.
        dia_select = frame_lvl1.locator("select[id*='DIA'], select[name*='DIA']")
        if await dia_select.count() > 0:
            fecha_objetivo = datetime.now() + timedelta(days=dias_desde_hoy)
            nombre_dia = {
                0: "LUNES",
                1: "MARTES",
                2: "MIERCOLES",
                3: "JUEVES",
                4: "VIERNES",
                5: "SABADO",
                6: "DOMINGO",
            }[fecha_objetivo.weekday()]
            candidatos = [
                nombre_dia,
                nombre_dia.capitalize(),
                nombre_dia[:3],
                nombre_dia[:3].capitalize(),
            ]
            seleccionado = False
            for opcion in candidatos:
                try:
                    await dia_select.first.select_option(label=opcion)
                    print(f"Día seleccionado en combo: {opcion}")
                    seleccionado = True
                    break
                except Exception:
                    continue
            if not seleccionado:
                print("No se pudo seleccionar el día por label. Se continuará filtrando por filas.")
        
        # 3. Seleccionar una fila que coincida con la fecha objetivo y horario requerido.
        print(f"Buscando horario exacto: {horario_objetivo}")
        filas = frame_lvl1.locator("tr[id^='Grid1ContainerRow']")
        total_filas = await filas.count()
        if total_filas == 0:
            return {
                "ok": False,
                "motivo": "sin_filas_horario",
                "detalle": "No hay filas de horario disponibles en Grid1ContainerRow.",
            }

        horario_norm = _normalizar_texto(horario_objetivo)
        patrones_fecha = {_normalizar_texto(p) for p in _patrones_fecha_objetivo(dias_desde_hoy)}

        fila_objetivo = None
        fila_texto = ""
        for idx in range(total_filas):
            fila = filas.nth(idx)
            texto_fila = _normalizar_texto(await fila.inner_text())
            contiene_horario = horario_norm in texto_fila
            contiene_fecha = any(p in texto_fila for p in patrones_fecha)
            if contiene_horario and contiene_fecha:
                fila_objetivo = fila
                fila_texto = texto_fila
                print(f"Fila exacta encontrada (fecha+hora) en índice {idx}.")
                break

        if fila_objetivo is None:
            print(
                f"No existe una fila exacta para fecha objetivo y horario permitido: {horario_objetivo}."
            )
            screenshot = await tomar_screenshots(
                page,
                f"6_horario_no_disponible_{horario_objetivo.replace(':', '_').replace(' ', '_')}",
            )
            return {
                "ok": False,
                "motivo": "horario_no_disponible",
                "detalle": f"No hubo match exacto para {horario_objetivo} y fecha objetivo.",
                "screenshot": screenshot,
            }

        await fila_objetivo.click()
        
        # 4. Clic en el botón Confirmar
        await frame_lvl1.locator("input[id$='BTNCONFIRMAR'], input[value='Confirmar']").click()
        
        # Esperamos a que el popup se cierre (GeneXus suele limpiar el DOM al terminar)
        await page.wait_for_selector("#gxp1_b", state="hidden", timeout=5000)
        return {
            "ok": True,
            "motivo": "ok",
            "detalle": "Horario confirmado correctamente.",
            "fila_texto": fila_texto,
        }
        
    except Exception as e:
        print(f"Error en la ventana de selección de horario: {e}")
        return {
            "ok": False,
            "motivo": "excepcion_seleccion_horario",
            "detalle": str(e),
        }