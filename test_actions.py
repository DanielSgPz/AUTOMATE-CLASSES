import unittest

from utils.actions import _detalle_error_programacion, _motivo_error_programacion, _separar_items_pendientes


class PendientesTest(unittest.TestCase):
    def test_separa_clases_e_items_informativos(self):
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

    def test_omite_las_sedes_del_detalle_de_cupo(self):
        detalle = _detalle_error_programacion(
            "Sede:\nGUACARI\nCENTRO\n\nTe invitamos a validar disponibilidad en otras "
            "franjas horarias o sedes cercanas. Recuerda que puedes ingresar continuamente "
            "y revisar los cupos que se liberan en el transcurso del día.\n\nClase Nro."
        )

        self.assertNotIn("GUACARI", detalle)
        self.assertIn("validar disponibilidad", detalle)


if __name__ == "__main__":
    unittest.main()
