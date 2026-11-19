"""Erreurs signalées à l'utilisateur."""


class ErreurConfiguration(Exception):
    """Dictionnaire, table ou arguments invalides : aucun fichier n'est traité."""


class ErreurDictionnaire(ErreurConfiguration):
    pass


class ErreurTable(ErreurConfiguration):
    pass


class ErreurFichier(Exception):
    """Un fichier ne peut pas être traité ; les autres le sont."""
