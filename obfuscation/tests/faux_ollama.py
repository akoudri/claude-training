"""Faux serveur Ollama : /api/tags liste des modèles, /api/chat renvoie les réponses programmées, dans l'ordre."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def reponse_chat(entites: list[dict]) -> dict:
    return {"message": {"role": "assistant", "content": json.dumps({"entites": entites})}, "done": True}


class FauxOllama:
    def __init__(self) -> None:
        self.modeles = ["granite4.2:8b"]
        self.reponses: list[tuple[int, dict | bytes, float]] = []  # (code HTTP, corps, attente en secondes)
        self.requetes: list[dict] = []
        etat = self

        class Gestionnaire(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def _repondre(self, code: int, corps: dict | bytes) -> None:
                donnees = corps if isinstance(corps, bytes) else json.dumps(corps).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(donnees)))
                self.end_headers()
                self.wfile.write(donnees)

            def do_GET(self) -> None:
                self._repondre(200, {"models": [{"name": nom} for nom in etat.modeles]})

            def do_POST(self) -> None:
                etat.requetes.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                code, corps, attente = etat.reponses.pop(0)
                time.sleep(attente)
                self._repondre(code, corps)

        self._serveur = ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
        self._serveur.daemon_threads = True
        self.url = f"http://127.0.0.1:{self._serveur.server_address[1]}"

    def demarrer(self) -> None:
        threading.Thread(target=self._serveur.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def arreter(self) -> None:
        self._serveur.shutdown()
        self._serveur.server_close()
