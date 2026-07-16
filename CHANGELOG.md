# Historial de cambios

## [2026-07-14] Iteración sobre hoy y mañana + detección de items especiales

**Problema original:** El sistema solo programaba para `dias_anticipacion=1` (mañana). Si se ejecutaba manualmente después de hacer un quiz, el día de hoy se quedaba sin clases.

**Solución:** Ahora itera sobre `dias_a_procesar = [0, 1]` (hoy y mañana). Evalúa primero qué días son válidos (día de clase + no festivo), hace login una vez, y por cada día válido abre el calendario, detecta horarios faltantes y los programa.

**Nuevo: Detección de items especiales en la lista de pendientes**

Cuando el sistema entra al módulo de programación y filtra por "Pendientes por programar", ahora clasifica cada item encontrado:

| Tipo | Patrón | Comportamiento |
|------|--------|----------------|
| `CLASE` | `^CLASE \d+` | Se programa automáticamente |
| `QUIZ` | `^QUIZ` | Se informa y se omite; no bloquea las `CLASE` pendientes. |
| `PREPARACIÓN EXAMEN FINAL` | `^(PREPARACIÓN\|PREPARACION) EXAMEN FINAL` | Se notifica, no se programa |
| `EXAMEN FINAL` | `^EXAMEN FINAL` | Se notifica, no se programa |
| `SMART ZONE` | `^SMART ZONE` | Se notifica, no se programa. **Listo para habilitar programación automática** cuando se den las reglas. |

Si no hay cupo en la primera franja requerida, se omite ese día para evitar matrículas parciales y se continúa con el siguiente día válido.
Si una franja habitual ya tiene una clase programada, se omite todo ese día para no matricular una sola clase.

## Pendiente: SMART ZONE

El detection point para SMART ZONE ya está implementado. Cuando se solicite activar la programación automática de SMART ZONE, se debe preguntar:

1. **¿En qué horario se programan?** (ej: fuera del horario de clases 18:00-21:00, en otro bloque)
2. **¿Se programan en la misma sede (GUACARI) o cambia?**
3. **¿Cantidad máxima por ejecución?** (igual que CLASEs = 2, o diferente)
4. **¿Aplican las mismas reglas de día de clase y festivos, o se programan cualquier día?**
5. **¿Deben respetar el orden de prioridad vs CLASEs?** (ej: programar SMART ZONE después de las CLASEs, o antes)

El código actual en `utils/actions.py:24-25` detecta SMART ZONE y lo omite. Para activarlo, se debe modificar `_clasificar_item_pendiente` y `programar_clases_pendientes` para que los SMART ZONE se programen como las CLASEs, con sus propias reglas de horario. Los patrones ya están definidos en las constantes `PATRON_SMART_ZONE`.
