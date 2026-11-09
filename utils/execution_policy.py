from datetime import time


PROGRAMMING_WINDOW_START = time(6, 0)
PROGRAMMING_WINDOW_END = time(22, 0)

RETRYABLE_TECHNICAL_REASONS = {
    "error_seleccion_horario",
    "error_validar_horario_dia_objetivo",
    "excepcion_no_controlada",
    "excepcion_programacion",
    "excepcion_seleccion_horario",
    "item_pendiente_no_encontrado",
    "no_fue_posible_iniciar_modulo_programacion",
    "no_fue_posible_navegar_a_programacion",
    "popup_no_cerro_tras_confirmar",
    "sin_popup_tras_asignar",
    "validacion_login_fallida",
}


def is_within_programming_window(moment) -> bool:
    """Smart permite matrículas desde las 06:00 hasta antes de las 22:00."""
    current_time = moment.time().replace(tzinfo=None)
    return PROGRAMMING_WINDOW_START <= current_time < PROGRAMMING_WINDOW_END


def target_offsets_for_run(profile, scheduled: bool) -> tuple[int, ...]:
    """La ejecución automática revisa hoy y mañana; las manuales respetan el perfil."""
    if scheduled:
        return (0, 1)
    return tuple(profile.target_day_offsets)


def is_retryable_technical_failure(report: dict) -> bool:
    if report.get("estado") not in {"error", "parcial"}:
        return False

    reasons = {report.get("motivo", "")}
    reasons.update(failure.get("motivo", "") for failure in report.get("fallos", []))
    return bool(reasons.intersection(RETRYABLE_TECHNICAL_REASONS))
