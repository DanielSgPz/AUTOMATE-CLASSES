import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from utils.telegram_notifier import construir_resumen_telegram, enviar_resumen_telegram


class TelegramReportTest(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 11, 12, 6, 5)
        self.end = datetime(2026, 11, 12, 6, 6)
        self.report = {
            "estado": "error",
            "motivo": "item_pendiente_no_encontrado",
            "fecha_objetivo": "2026-11-12",
            "programadas": [],
            "planificadas": [],
            "fallos": [],
            "total_encontradas": 402,
            "items_especiales": [
                {"tipo": "quiz", "nombre": "QUIZ UNITS 1*2 - A2", "cantidad": 1},
            ],
            "horarios_consultados": [{
                "fecha": "2026-11-12",
                "ocupados": ["18:00 19:30"],
                "faltantes": ["19:30 21:00"],
                "screenshot": "screenshots/horario.png",
            }],
        }

    def test_hides_informational_items_and_shows_schedule(self):
        message = construir_resumen_telegram(self.report, self.start, self.end)

        self.assertNotIn("Items pendientes", message)
        self.assertNotIn("QUIZ UNITS", message)
        self.assertIn("Horarios consultados", message)
        self.assertIn("18:00 19:30", message)
        self.assertIn("19:30 21:00", message)

    @patch("utils.telegram_notifier.os.path.exists", return_value=True)
    @patch("utils.telegram_notifier.enviar_foto_telegram")
    @patch("utils.telegram_notifier.enviar_mensaje_telegram", return_value=True)
    def test_sends_schedule_screenshot_even_on_error(
        self,
        message_mock,
        photo_mock,
        exists_mock,
    ):
        config = SimpleNamespace(bot_token="token", chat_id="chat")

        enviar_resumen_telegram(config, self.report, self.start, self.end)

        message_mock.assert_called_once()
        photo_mock.assert_called_once_with(
            "token",
            "chat",
            "screenshots/horario.png",
            caption="🗓️ Horario del 2026-11-12",
        )
