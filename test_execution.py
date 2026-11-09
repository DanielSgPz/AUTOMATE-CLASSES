import unittest
from unittest.mock import AsyncMock, Mock, patch

from main import workflow_programado_con_reintentos


def _report(state, reason):
    return {
        "estado": state,
        "motivo": reason,
        "programadas": [],
        "fallos": [{"motivo": reason}] if state == "error" else [],
    }


class ScheduledRetryTest(unittest.IsolatedAsyncioTestCase):
    @patch("main.enviar_resumen_telegram")
    @patch("main.load_telegram_config")
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.workflow_principal", new_callable=AsyncMock)
    async def test_retries_technical_errors_and_notifies_only_once(
        self,
        workflow_mock,
        sleep_mock,
        telegram_config_mock,
        telegram_send_mock,
    ):
        workflow_mock.side_effect = [
            _report("error", "validacion_login_fallida"),
            _report("error", "excepcion_programacion"),
            _report("exito", "horario_completo_para_dias_objetivo"),
        ]
        telegram_config_mock.return_value = Mock()

        result = await workflow_programado_con_reintentos(retry_delay_seconds=600)

        self.assertEqual(workflow_mock.await_count, 3)
        self.assertEqual(sleep_mock.await_count, 2)
        sleep_mock.assert_awaited_with(600)
        telegram_send_mock.assert_called_once()
        self.assertEqual(result["intentos"], 3)
        self.assertEqual(result["reintentos"], 2)
        self.assertTrue(result["recuperado_tras_reintentos"])

    @patch("main.enviar_resumen_telegram")
    @patch("main.load_telegram_config")
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.workflow_principal", new_callable=AsyncMock)
    async def test_does_not_retry_a_business_result(
        self,
        workflow_mock,
        sleep_mock,
        telegram_config_mock,
        telegram_send_mock,
    ):
        workflow_mock.return_value = _report("error", "sin_cupo")
        telegram_config_mock.return_value = Mock()

        result = await workflow_programado_con_reintentos(retry_delay_seconds=600)

        self.assertEqual(workflow_mock.await_count, 1)
        sleep_mock.assert_not_awaited()
        telegram_send_mock.assert_called_once()
        self.assertEqual(result["intentos"], 1)


if __name__ == "__main__":
    unittest.main()
