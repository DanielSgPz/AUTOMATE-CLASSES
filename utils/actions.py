import os
import re
from datetime import timedelta

from utils.timezone import now_colombia

HORARIOS_PERMITIDOS = ["18:00 19:30", "19:30 21:00"]

PATRON_QUIZ = re.compile(r'^QUIZ', re.IGNORECASE)
PATRON_PREP_EXAMEN = re.compile(r'^(PREPARACIÓN|PREPARACION)\s+EXAMEN\s+FINAL', re.IGNORECASE)
PATRON_EXAMEN_FINAL = re.compile(r'^EXAMEN\s+FINAL', re.IGNORECASE)
PATRON_SMART_ZONE = re.compile(r'^SMART\s+ZONE', re.IGNORECASE)
PATRON_CLASE = re.compile(r'^CLASE\s+\d+')


def _clasificar_item_pendiente(texto):
    texto_norm = texto.strip().upper()
    if PATRON_QUIZ.match(texto_norm):
        return "quiz"
    if PATRON_PREP_EXAMEN.match(texto_norm):
        return "preparacion_examen_final"
    if PATRON_EXAMEN_FINAL.match(texto_norm):
        return "examen_final"
    if PATRON_SMART_ZONE.match(texto_norm):
        return "smart_zone"
    if PATRON_CLASE.match(texto_norm):
        return "clase"
    return "otro"


def _separar_items_pendientes(textos):
    clases = []
    especiales = []
    for texto in textos:
        tipo = _clasificar_item_pendiente(texto)
        if tipo == "clase":
            clases.append(texto)
        elif tipo != "otro":
            especiales.append({"tipo": tipo, "nombre": texto})
    return clases, especiales


def _motivo_error_programacion(mensaje):
    mensaje = _normalizar_texto(mensaje)
    if "CUPO" in mensaje or "DISPONIB" in mensaje:
        return "sin_cupo"
    if "FECHAS FUTURAS" in mensaje or "CLASES ANTERIORES PROGRAMADAS" in mensaje:
        return "clases_futuras_pendientes"
    return "popup_no_cerro_tras_confirmar"


def _detalle_error_programacion(mensaje):
    for patron in (
        r"(Te invitamos a validar disponibilidad.*?día\.)",
        r"(La clase no puede ser programada.*?fechas futuras\.)",
    ):
        coincidencia = re.search(patron, mensaje, re.IGNORECASE | re.DOTALL)
        if coincidencia:
            return re.sub(r"\s+", " ", coincidencia.group(1)).strip()
    return "El popup seguía abierto después de confirmar."


def _normalizar_texto(texto):
    return re.sub(r"\s+", " ", texto).strip().upper()


def _patrones_fecha_objetivo(dias_desde_hoy=1):
    fecha_objetivo = now_colombia() + timedelta(days=dias_desde_hoy)
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
    fecha_objetivo = now_colombia() + timedelta(days=dias_desde_hoy)
    return fecha_objetivo.strftime("%Y-%m-%d")


def _normalizar_rango_horario(inicio, fin):
    """Convierte '18:00' + '19:30' a '18:00 19:30'."""
    inicio_partes = inicio.strip().split(":")
    fin_partes = fin.strip().split(":")
    inicio_norm = f"{int(inicio_partes[0]):02d}:{int(inicio_partes[1]):02d}"
    fin_norm = f"{int(fin_partes[0]):02d}:{int(fin_partes[1]):02d}"
    return f"{inicio_norm} {fin_norm}"


def _inicio_horario(rango):
    """Extrae la hora de inicio desde un rango 'HH:MM HH:MM'."""
    return rango.strip().split()[0]


def _normalizar_hora(hora):
    """Normaliza hora flexible (ej: '9:0' -> '09:00')."""
    partes = hora.strip().split(":")
    return f"{int(partes[0]):02d}:{int(partes[1]):02d}"

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


async def validar_horario_dia_objetivo(page, dias_desde_hoy=1, horarios_habituales=None, nombre_screenshot="horario_dia_objetivo"):
    """
    Abre la ventana 'Horario', navega al día objetivo y detecta qué franjas del horario
    habitual ya están ocupadas. Retorna las franjas faltantes que deben programarse.
    """
    if horarios_habituales is None:
        horarios_habituales = list(HORARIOS_PERMITIDOS)

    try:
        print("Abriendo ventana de Horario para validar clases ya programadas...")
        await page.click("#BUTTON2")
        await page.wait_for_selector("#gxp0_b", state="visible", timeout=10000)

        frame = page.frame_locator("#gxp0_ifrm")
        await frame.locator(".dhx_cal_next_button").wait_for(state="visible", timeout=10000)

        # Intentar cambiar a vista de día para que cada clic en "siguiente" avance un día.
        # En vista semanal, un clic avanzaría 7 días (semana completa) en lugar de 1 día.
        try:
            day_tab = frame.locator("[name='day_tab']")
            if await day_tab.count() > 0:
                await day_tab.first.click()
                await page.wait_for_timeout(800)
                print("Calendario cambiado a vista de día.")
        except Exception:
            print("No se pudo cambiar a vista de día; se continúa con la vista actual.")

        for _ in range(dias_desde_hoy):
            await frame.locator(".dhx_cal_next_button").click()
            await page.wait_for_timeout(1200)

        fecha_referencia = "(no detectada)"
        try:
            fecha_referencia = (await frame.locator(".dhx_cal_date").first.inner_text()).strip()
        except Exception:
            try:
                fecha_referencia = (await frame.locator(".dhx_scale_bar").first.inner_text()).strip()
            except Exception:
                pass

        print(f"Calendario posicionado en: {fecha_referencia}")

        eventos = frame.locator(".dhx_cal_event .dhx_title")
        total_eventos = await eventos.count()
        horarios_ocupados = set()
        horario_por_inicio = {_inicio_horario(h): h for h in horarios_habituales}

        for idx in range(total_eventos):
            titulo = (await eventos.nth(idx).inner_text()).strip()
            match = re.search(r"\((\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\)", titulo)
            if not match:
                continue
            inicio = match.group(1)
            fin = match.group(2)
            rango = _normalizar_rango_horario(inicio, fin)

            # Match ideal: rango exacto en horario habitual.
            if rango in horarios_habituales:
                horarios_ocupados.add(rango)
                continue

            # Fallback: algunos eventos se renderizan truncados (ej: 19:30-20:00),
            # pero siguen ocupando el bloque habitual de inicio 19:30.
            inicio_norm = _normalizar_hora(inicio)
            if inicio_norm in horario_por_inicio:
                horarios_ocupados.add(horario_por_inicio[inicio_norm])

        horarios_faltantes = [h for h in horarios_habituales if h not in horarios_ocupados]

        # Para evidencia visual, desplazar el calendario al final dentro del iframe
        # y mostrar las franjas de tarde/noche (donde suelen estar 18:00 y 19:30).
        try:
            iframe_el = page.locator("#gxp0_ifrm")
            await iframe_el.wait_for(state="attached", timeout=3000)
            iframe_handle = await iframe_el.element_handle()
            if iframe_handle is not None:
                iframe_page = await iframe_handle.content_frame()
                if iframe_page is not None:
                    await iframe_page.evaluate(
                        """
                        () => {
                            const objetivos = [
                                document.querySelector('.dhx_cal_data'),
                                document.querySelector('.dhx_cal_data .dhx_scale_holder'),
                                document.scrollingElement,
                                document.documentElement,
                                document.body,
                            ].filter(Boolean);

                            for (const el of objetivos) {
                                try {
                                    el.scrollTop = el.scrollHeight;
                                } catch (_) {
                                    // no-op
                                }
                            }
                        }
                        """
                    )
                    await page.wait_for_timeout(300)
        except Exception:
            print("No se pudo ajustar el scroll interno del calendario para el screenshot.")

        screenshot = await tomar_screenshots(page, nombre_screenshot)

        return {
            "ok": True,
            "motivo": "ok",
            "detalle": "Horario del día objetivo consultado correctamente.",
            "fecha_referencia": fecha_referencia,
            "horarios_ocupados": sorted(horarios_ocupados),
            "horarios_faltantes": horarios_faltantes,
            "cantidad_a_programar": len(horarios_faltantes),
            "screenshot": screenshot,
        }
    except Exception as e:
        print(f"Error validando horario del día objetivo: {e}")
        screenshot = await tomar_screenshots(page, "error_validar_horario_dia_objetivo")
        return {
            "ok": False,
            "motivo": "error_validar_horario_dia_objetivo",
            "detalle": str(e),
            "horarios_ocupados": [],
            "horarios_faltantes": [],
            "cantidad_a_programar": 0,
            "screenshot": screenshot,
        }
    finally:
        try:
            if await page.locator("#gxp0_b").is_visible():
                await page.click("#gxp0_cls")
                await page.wait_for_selector("#gxp0_b", state="hidden", timeout=5000)
        except Exception:
            pass
    
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
    
    
async def programar_clases_pendientes(page, cantidad=2, sede="GUACARI", dias_desde_hoy=1, horarios_objetivo=None):
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
        "items_especiales": [],
        "avisos": [],
    }
    try:
        if horarios_objetivo is None:
            horarios_objetivo = list(HORARIOS_PERMITIDOS[:cantidad])

        if cantidad > len(horarios_objetivo):
            print(
                f"La cantidad solicitada ({cantidad}) supera los horarios objetivo ({len(horarios_objetivo)})."
            )
            screenshot = await tomar_screenshots(page, "error_cantidad_vs_horarios_objetivo")
            resultado["fallos"].append({
                "motivo": "cantidad_supera_horarios_objetivo",
                "detalle": f"Solicitadas={cantidad}, HorariosObjetivo={len(horarios_objetivo)}",
                "screenshot": screenshot,
            })
            return resultado

        frame = page.frame_locator("#gxp0_ifrm")

        # 1. Filtramos por "Pendientes por programar" (valor 2)
        dropdown = frame.locator("#vTPEAPROBO")
        await dropdown.select_option("2")
        await page.wait_for_timeout(2000) # Esperamos el refresco AJAX

        # 2. Primer pase: clasificar todos los items pendientes
        todos_items = frame.locator("span[id^='span_vPRONOMPRO']")
        total_items = await todos_items.count()
        resultado["total_encontradas"] = total_items
        print(f"Se encontraron {total_items} items pendientes.")

        textos_pendientes = []
        for j in range(total_items):
            texto = (await todos_items.nth(j).inner_text()).strip()
            textos_pendientes.append(texto)

        items_clase, items_especiales = _separar_items_pendientes(textos_pendientes)
        for item in items_especiales:
            print(f"Item especial detectado: [{item['tipo']}] {item['nombre']}")

        resultado["items_especiales"] = items_especiales

        if not items_clase:
            if items_especiales:
                print("No hay CLASEs pendientes; solo hay items especiales.")
                resultado["avisos"].append({
                    "motivo": "sin_clases_programables",
                    "detalle": "No se matricularon CLASEs porque solo hay quiz, examen o Smart Zone pendientes.",
                })
            else:
                print("No hay clases para programar hoy.")
                screenshot = await manejar_dia_sin_horarios(page, cerrar_popup=False)
                resultado["fallos"].append({
                    "motivo": "sin_clases_pendientes",
                    "detalle": "No se encontraron clases pendientes para el día objetivo.",
                    "screenshot": screenshot,
                })
            return resultado

        # 3. Iteramos para programar la cantidad deseada.
        # Usamos while + re-consulta del DOM en cada vuelta porque al programar una clase
        # ésta desaparece de la lista "pendientes", desplazando los índices.
        programadas = 0
        clases_ya_intentadas = set()
        while programadas < cantidad:
            clases_pendientes = frame.locator("span[id^='span_vPRONOMPRO']")
            total_disponibles = await clases_pendientes.count()

            clase_actual = None
            nombre_clase = ""
            for j in range(total_disponibles):
                candidato = clases_pendientes.nth(j)
                texto = (await candidato.inner_text()).strip()
                if PATRON_CLASE.match(texto):
                    if texto in clases_ya_intentadas:
                        continue
                    clase_actual = candidato
                    nombre_clase = texto
                    break

            if clase_actual is None:
                print("No se encontraron más clases CLASE para programar.")
                break

            clases_ya_intentadas.add(nombre_clase)

            print(f"Programando automáticamente: {nombre_clase}")
            await clase_actual.click()
            await tomar_screenshots(
                page,
                f"6_clase_seleccionada_dia_{dias_desde_hoy}_{nombre_clase.replace(' ', '_').lower()}",
            )
            await frame.locator("#BUTTON1").dispatch_event("click")

            # Esperamos a que aparezca el popup de respuesta del sistema.
            try:
                await page.wait_for_selector("#gxp1_b", state="visible", timeout=7000)
            except Exception:
                print("No apareció ningún popup tras hacer clic en Asignar.")
                screenshot = await tomar_screenshots(page, f"6_sin_popup_clase_{programadas + 1}")
                resultado["fallos"].append({
                    "clase": nombre_clase,
                    "hora_objetivo": horarios_objetivo[programadas],
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
                    "hora_objetivo": horarios_objetivo[programadas],
                    "motivo": "fuera_de_horario_programacion",
                    "detalle": f"Popup recibido: {titulo_popup}",
                    "screenshot": screenshot,
                })
                return resultado

            horario_objetivo = horarios_objetivo[programadas]
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
                    "screenshot": seleccion.get("screenshot"),
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
        screenshot = await tomar_screenshots(page, "error_programar_clases_pendientes")
        resultado["fallos"].append({
            "motivo": "excepcion_programacion",
            "detalle": str(e),
            "screenshot": screenshot,
        })
        return resultado
    
    
async def seleccionar_horario_especifico(page, sede="GUACARI", horario_objetivo="18:00 19:30", dias_desde_hoy=1):
    """
    Maneja el popup de segundo nivel (gxp1_ifrm) para confirmar la sede, dia y hora.
    """
    try:
        frame_lvl1 = page.frame_locator("#gxp1_ifrm")

        # Esperamos a que el iframe cargue su contenido antes de interactuar
        await frame_lvl1.locator("select").first.wait_for(state="visible", timeout=15000)

        # 1. Seleccionar la Sede (best-effort: si falla, continuamos)
        print(f"Seleccionando sede: {sede}")
        try:
            sede_select = frame_lvl1.locator(
                "select[id$='vSEDEID'], select[id*='SEDE'], select[name*='SEDE']"
            )
            if await sede_select.count() > 0:
                await sede_select.first.select_option(label=sede)
                await page.wait_for_timeout(1500)
                print(f"Sede '{sede}' seleccionada.")
            else:
                print("No se encontró el selector de sede, continuando con la sede actual.")
        except Exception as e:
            print(f"No se pudo seleccionar sede (continuando con la actual): {e}")

        # 2. Seleccionar el día objetivo (mañana).
        # El dropdown muestra etiquetas con fecha completa, ej: "Viernes 15/05/26"
        # por lo que incluimos ese formato como candidato principal.
        # dia_seleccionado=True significa que el dropdown ya filtró por fecha,
        # por lo que las filas solo contienen la hora (no la fecha).
        dia_seleccionado = False
        dia_select = frame_lvl1.locator("select[id*='DIA'], select[name*='DIA']")
        if await dia_select.count() > 0:
            fecha_objetivo = now_colombia() + timedelta(days=dias_desde_hoy)
            nombre_dia = {
                0: "LUNES",
                1: "MARTES",
                2: "MIERCOLES",
                3: "JUEVES",
                4: "VIERNES",
                5: "SABADO",
                6: "DOMINGO",
            }[fecha_objetivo.weekday()]
            fecha_dd_mm_yy = fecha_objetivo.strftime("%d/%m/%y")
            candidatos = [
                f"{nombre_dia.capitalize()} {fecha_dd_mm_yy}",  # "Viernes 15/05/26"
                f"{nombre_dia} {fecha_dd_mm_yy}",               # "VIERNES 15/05/26"
                nombre_dia,
                nombre_dia.capitalize(),
                nombre_dia[:3],
                nombre_dia[:3].capitalize(),
            ]
            for opcion in candidatos:
                try:
                    await dia_select.first.select_option(label=opcion)
                    print(f"Día seleccionado en combo: {opcion}")
                    dia_seleccionado = True
                    break
                except Exception:
                    continue
            if dia_seleccionado:
                await page.wait_for_timeout(2000)  # Esperar refresco AJAX tras cambio de día
            else:
                print("No se pudo seleccionar el día por label. Se continuará filtrando por filas.")

        # 3. Seleccionar una fila que coincida con el horario requerido.
        # Si el dropdown de día ya filtró la fecha, solo se valida la hora.
        # Si no se pudo seleccionar el día, se valida también la fecha en el texto de la fila.
        print(f"Buscando horario exacto: {horario_objetivo}")
        filas = frame_lvl1.locator("tr[id^='Grid1ContainerRow']")
        total_filas = await filas.count()
        if total_filas == 0:
            print("Sin filas de horario disponibles: no hay clases programadas para ese día.")
            screenshot = await manejar_dia_sin_horarios(page, cerrar_popup=True)
            return {
                "ok": False,
                "motivo": "sin_horarios_para_dia_objetivo",
                "detalle": "No hay horarios disponibles para el día objetivo. La academia no tiene clases ese día.",
                "screenshot": screenshot,
            }

        horario_norm = _normalizar_texto(horario_objetivo)
        patrones_fecha = {_normalizar_texto(p) for p in _patrones_fecha_objetivo(dias_desde_hoy)}

        fila_objetivo = None
        fila_texto = ""
        for idx in range(total_filas):
            fila = filas.nth(idx)
            texto_fila = _normalizar_texto(await fila.inner_text())
            contiene_horario = horario_norm in texto_fila
            # Si el día ya fue seleccionado en el dropdown, la grilla ya filtró por fecha
            # y las filas solo muestran horas → solo validamos la hora.
            # Si no se seleccionó el día, validamos también que la fecha aparezca en la fila.
            contiene_fecha = dia_seleccionado or any(p in texto_fila for p in patrones_fecha)
            if contiene_horario and contiene_fecha:
                fila_objetivo = fila
                fila_texto = texto_fila
                print(f"Fila exacta encontrada (hora) en índice {idx}: {texto_fila}")
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
        
        # Verificar si el popup se cerró correctamente tras Confirmar
        try:
            await page.wait_for_selector("#gxp1_b", state="hidden", timeout=5000)
            return {
                "ok": True,
                "motivo": "ok",
                "detalle": "Horario confirmado correctamente.",
                "fila_texto": fila_texto,
            }
        except Exception:
            # Leer el mensaje de error antes de decidir si se intenta otra franja.
            motivo_fallo = "popup_no_cerro_tras_confirmar"
            detalle_fallo = "El popup seguía abierto después de hacer clic en Confirmar."
            try:
                msg = (await frame_lvl1.locator("body").inner_text()).strip()
                if msg:
                    motivo_fallo = _motivo_error_programacion(msg)
                    detalle_fallo = _detalle_error_programacion(msg)
                    print(f"Error del sistema: {detalle_fallo}")
            except Exception:
                pass

            print(f"El popup no se cerró tras Confirmar ({motivo_fallo}). Tomando evidencia...")
            screenshot = await tomar_screenshots(page, f"confirmar_{motivo_fallo}")

            # Cerrar el popup para no bloquear el siguiente día.
            try:
                await page.click("#gxp1_cls")
                await page.wait_for_selector("#gxp1_b", state="hidden", timeout=3000)
            except Exception:
                pass

            return {
                "ok": False,
                "motivo": motivo_fallo,
                "detalle": detalle_fallo,
                "screenshot": screenshot,
            }
        
    except Exception as e:
        print(f"Error en la ventana de selección de horario: {e}")
        screenshot = await tomar_screenshots(page, "error_seleccion_horario")
        return {
            "ok": False,
            "motivo": "excepcion_seleccion_horario",
            "detalle": str(e),
            "screenshot": screenshot,
        }

async def manejar_dia_sin_horarios(page, cerrar_popup=False):
    """
    Maneja el caso donde no hay horarios disponibles para programar.
    Toma un pantallazo, informa que no hay horarios y opcionalmente cierra el popup.
    Retorna la ruta del screenshot para incluirla en el informe.
    """
    print("No hay horarios disponibles para el día seleccionado.")

    screenshot_path = await tomar_screenshots(page, "no_horarios_disponibles")
    print(f"Evidencia guardada en: {screenshot_path}")

    if cerrar_popup:
        try:
            cerrar_boton = page.locator("#gxp1_cls")
            await cerrar_boton.wait_for(state="visible", timeout=3000)
            await cerrar_boton.click()
            await page.wait_for_selector("#gxp1_b", state="hidden", timeout=5000)
            print("Popup cerrado exitosamente.")
        except Exception as e:
            print(f"No fue posible cerrar el popup: {e}")

    return screenshot_path
