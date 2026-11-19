"""Adaptateurs de formats : chacun applique le moteur au texte d'un type de fichier."""
from dataclasses import dataclass, field


@dataclass
class Resultat:
    donnees: bytes
    avertissements: list[str] = field(default_factory=list)
