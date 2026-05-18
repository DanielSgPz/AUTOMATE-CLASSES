import holidays
from datetime import timedelta

from utils.timezone import now_colombia


def evaluar_programacion_hoy(dias_anticipacion=1):
    """
    Determina si hoy es el día correcto para ejecutar la programación
    con antelación configurable (por defecto: mañana) y festivos.
    """
    co_holidays = holidays.Colombia()
    hoy = now_colombia().date()
    fecha_objetivo = hoy + timedelta(days=dias_anticipacion)

    dia_objetivo = fecha_objetivo.weekday()  # 0=Lunes, 1=Martes...

    # Tus días de clase: Lunes(0), Martes(1), Jueves(3), Viernes(4)
    dias_clase = [0, 1, 3, 4]

    print(
        f"Hoy es {hoy.strftime('%A')}. "
        f"Evaluando clase para el {fecha_objetivo.strftime('%B %d')} "
        f"(anticipación: {dias_anticipacion} día[s])."
    )

    # REGLA 1: ¿Hay clase en la fecha objetivo?
    if dia_objetivo not in dias_clase:
        print(f"La fecha objetivo ({fecha_objetivo.strftime('%A')}) no es día de clase. Saltando ejecución.")
        return {
            "ok": False,
            "motivo": "no_dia_de_clase",
            "detalle": "La fecha objetivo no corresponde a Lunes, Martes, Jueves o Viernes.",
            "hoy": hoy.isoformat(),
            "fecha_objetivo": fecha_objetivo.isoformat(),
        }

    # REGLA 2: ¿La fecha objetivo es festivo en Colombia?
    if fecha_objetivo in co_holidays:
        festivo = co_holidays.get(fecha_objetivo)
        print(f"La fecha objetivo es festivo ({festivo}). No hay clases.")
        return {
            "ok": False,
            "motivo": "festivo_colombia",
            "detalle": f"La fecha objetivo es festivo en Colombia: {festivo}.",
            "hoy": hoy.isoformat(),
            "fecha_objetivo": fecha_objetivo.isoformat(),
        }

    print("¡Condiciones cumplidas! Iniciando proceso de automatización...")
    return {
        "ok": True,
        "motivo": "ok",
        "detalle": "La fecha objetivo es día de clase y no es festivo.",
        "hoy": hoy.isoformat(),
        "fecha_objetivo": fecha_objetivo.isoformat(),
    }


def debe_programar_hoy(dias_anticipacion=1):
    return evaluar_programacion_hoy(dias_anticipacion=dias_anticipacion)["ok"]