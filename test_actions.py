import unittest

from utils.actions import _motivo_error_programacion, _separar_items_pendientes


class PendientesTest(unittest.TestCase):
    def test_las_clases_no_son_bloqueadas_por_quiz_o_examen(self):
        clases, especiales = _separar_items_pendientes([
            "QUIZ 1",
            "EXAMEN FINAL",
            "CLASE 12",
            "SMART ZONE 1",
            "CLASE 13",
        ])

        self.assertEqual(clases, ["CLASE 12", "CLASE 13"])
        self.assertEqual(
            [item["tipo"] for item in especiales],
            ["quiz", "examen_final", "smart_zone"],
        )

    def test_detecta_el_mensaje_de_cupo_lleno(self):
        self.assertEqual(
            _motivo_error_programacion("No hay cupos disponibles para este horario."),
            "sin_cupo",
        )


if __name__ == "__main__":
    unittest.main()
