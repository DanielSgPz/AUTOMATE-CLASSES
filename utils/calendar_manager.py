import holidays
from datetime import datetime, timedelta

def debe_programar_hoy(dias_anticipacion=1):
    """
    Determina si hoy es el día correcto para ejecutar la programación
    con antelación configurable (por defecto: mañana) y festivos.
    """
    co_holidays = holidays.Colombia()
    hoy = datetime.now().date()
    fecha_objetivo = hoy + timedelta(days=dias_anticipacion)
    
    dia_objetivo = fecha_objetivo.weekday() # 0=Lunes, 1=Martes...
    
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
        return False

    # REGLA 2: ¿La fecha objetivo es festivo en Colombia?
    if fecha_objetivo in co_holidays:
        print(f"La fecha objetivo es festivo ({co_holidays.get(fecha_objetivo)}). No hay clases.")
        return False

    print("¡Condiciones cumplidas! Iniciando proceso de automatización...")
    return True