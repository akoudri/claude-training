"""Tests de la synchronisation du moteur d'extraction (python3 -m unittest, depuis local-llm/open-webui)."""
import unittest

from configurer import Echec, docling_depuis_env, reglage_extraction

DOCLING = {"url": "http://docling:5001", "params": {"do_ocr": "false", "table_mode": "accurate"}}
ALIGNE = {
    "CONTENT_EXTRACTION_ENGINE": "docling",
    "DOCLING_SERVER_URL": "http://docling:5001",
    "DOCLING_PARAMS": {"do_ocr": "false", "table_mode": "accurate"},
}


class ReglageExtraction(unittest.TestCase):
    def test_overlay_config_differente(self):
        champs, etat = reglage_extraction({"CONTENT_EXTRACTION_ENGINE": "", "DOCLING_PARAMS": {}}, DOCLING)
        self.assertEqual(champs, ALIGNE)
        self.assertEqual(etat, "Docling (réglé)")

    def test_overlay_parametres_changes(self):
        config = {**ALIGNE, "DOCLING_PARAMS": {"do_ocr": "true"}}
        champs, _ = reglage_extraction(config, DOCLING)
        self.assertEqual(champs, ALIGNE)

    def test_overlay_deja_aligne(self):
        self.assertEqual(reglage_extraction(dict(ALIGNE), DOCLING), (None, "Docling (inchangé)"))

    def test_sans_overlay_moteur_docling(self):
        champs, etat = reglage_extraction(dict(ALIGNE), None)
        self.assertEqual(champs, {"CONTENT_EXTRACTION_ENGINE": ""})
        self.assertEqual(etat, "extracteur intégré (Docling retiré)")

    def test_sans_overlay_extracteur_integre(self):
        self.assertEqual(reglage_extraction({"CONTENT_EXTRACTION_ENGINE": ""}, None),
                         (None, "extracteur intégré (inchangé)"))

    def test_sans_overlay_autre_moteur(self):
        self.assertEqual(reglage_extraction({"CONTENT_EXTRACTION_ENGINE": "tika"}, None), (None, "tika (inchangé)"))

    def test_config_sans_cle_moteur(self):
        self.assertEqual(reglage_extraction({}, None), (None, "extracteur intégré (inchangé)"))
        champs, _ = reglage_extraction({}, DOCLING)
        self.assertEqual(champs, ALIGNE)


class DoclingDepuisEnv(unittest.TestCase):
    def test_overlay_absent(self):
        self.assertIsNone(docling_depuis_env({}))
        self.assertIsNone(docling_depuis_env({"OPENWEBUI_DOCLING": "false"}))

    def test_overlay_present(self):
        env = {"OPENWEBUI_DOCLING": "True", "DOCLING_SERVER_URL": "http://docling:5001",
               "DOCLING_PARAMS": '{"do_ocr": "false", "table_mode": "accurate"}'}
        self.assertEqual(docling_depuis_env(env), DOCLING)

    def test_parametres_absents(self):
        env = {"OPENWEBUI_DOCLING": "true", "DOCLING_SERVER_URL": "http://docling:5001"}
        self.assertEqual(docling_depuis_env(env), {"url": "http://docling:5001", "params": {}})

    def test_parametres_json_invalides(self):
        env = {"OPENWEBUI_DOCLING": "true", "DOCLING_SERVER_URL": "http://docling:5001", "DOCLING_PARAMS": "{do_ocr"}
        with self.assertRaisesRegex(Echec, "DOCLING_PARAMS"):
            docling_depuis_env(env)

    def test_parametres_pas_un_objet(self):
        env = {"OPENWEBUI_DOCLING": "true", "DOCLING_SERVER_URL": "http://docling:5001", "DOCLING_PARAMS": "[1]"}
        with self.assertRaisesRegex(Echec, "DOCLING_PARAMS"):
            docling_depuis_env(env)

    def test_url_absente(self):
        with self.assertRaisesRegex(Echec, "DOCLING_SERVER_URL"):
            docling_depuis_env({"OPENWEBUI_DOCLING": "true"})


if __name__ == "__main__":
    unittest.main()
