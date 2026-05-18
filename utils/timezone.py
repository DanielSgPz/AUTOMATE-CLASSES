from datetime import datetime
from zoneinfo import ZoneInfo


COLOMBIA_TZ = ZoneInfo("America/Bogota")


def now_colombia() -> datetime:
    return datetime.now(COLOMBIA_TZ)
