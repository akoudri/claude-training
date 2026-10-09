"""Génère matrice-acteurs-heron.pdf, PDF fictif du Projet Héron pour comparer les extracteurs d'Open WebUI.

Le document réunit ce que l'extracteur intégré lit mal (tutoriel 01, section 6.2) : un sommaire, des tableaux à
plusieurs colonnes aux valeurs proches d'une ligne à l'autre, un pied de page répété sur chaque page.

Depuis local-llm/ : uv run --with reportlab==5.0.1 open-webui/exemples/generer-pdf.py
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SORTIE = Path(__file__).with_name("matrice-acteurs-heron.pdf")
PAGES = 3
STYLES = getSampleStyleSheet()

# Cellules sur plusieurs lignes et cellules vides : une fois le tableau aplati, plus rien n'indique à quelle colonne
# appartient une valeur.
ACTEURS = [
    ["Organisation", "Rôle", "Classification des données", "Accès au référentiel SysML", "Statut"],
    ["Acme Défense", "Maître d'ouvrage, direction de l'ingénierie système", "Niveau 3", "Lecture/écriture", "Validé"],
    ["Novaltis", "Titulaire du marché, pilotage et réalisation", "Niveau 2", "Lecture/écriture", "Validé"],
    ["Orbitec Systèmes", "Sous-traitant outillage et intégration continue", "Niveau 1", "", "En attente"],
    ["Bureau Vertex", "Audit qualité indépendant", "Niveau 2", "Lecture seule", "Validé"],
    ["Kerlan Ingénierie", "Expertise SysML v2, appui ponctuel sur demande", "", "Lecture seule", "En attente"],
    ["Direction des achats d'Acme Défense", "Suivi contractuel et facturation", "Niveau 3", "", "Validé"],
]
LIVRABLES = [
    ["Livrable", "Exigence", "Responsable", "Relecteur", "Échéance"],
    ["Rapport d'inventaire des modèles", "EX-01", "Novaltis", "Acme Défense", "Mois 2"],
    ["Plan de migration", "EX-05", "Novaltis", "Bureau Vertex", "Mois 6"],
    ["Rapport final", "EX-08", "Novaltis", "Acme Défense", "Mois 9"],
    ["Guide de modélisation mis à jour", "EX-10", "Acme Défense", "Novaltis", "Mois 10"],
]


def tableau(lignes, largeurs):
    cellule = STYLES["BodyText"].clone("cellule", fontSize=9, leading=11)
    entete = cellule.clone("entete", fontName="Helvetica-Bold")
    lignes = [[Paragraph(v, entete if i == 0 else cellule) for v in ligne] for i, ligne in enumerate(lignes)]
    t = Table(lignes, colWidths=[l * cm for l in largeurs], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def pied_de_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm,
                             f"Projet Héron – Diffusion restreinte – © Novaltis 2026 – page {doc.page}/{PAGES}")
    canvas.restoreState()


def contenu():
    titre, h1, texte = STYLES["Title"], STYLES["Heading1"], STYLES["BodyText"]
    return [
        Paragraph("Projet Héron – Annexe C : matrice des acteurs et des livrables", titre),
        Paragraph("Document fictif, établi pour les exercices de la formation.", texte),
        Spacer(1, 0.6 * cm),
        Paragraph("Sommaire", h1),
        Paragraph("1. Objet de l'annexe", texte),
        Paragraph("2. Acteurs et classification des données", texte),
        Paragraph("3. Livrables et responsables", texte),
        Paragraph("4. Calendrier", texte),
        Spacer(1, 0.6 * cm),
        Paragraph("1. Objet de l'annexe", h1),
        Paragraph("Cette annexe complète la proposition technique de Novaltis pour la migration des modèles "
                  "SysML v1 d'Acme Défense vers SysML v2. Elle précise, pour chaque organisation, son rôle, le "
                  "niveau de classification des données qu'elle manipule et ses droits sur le référentiel de "
                  "modèles, puis répartit les livrables contractuels.", texte),
        PageBreak(),
        Paragraph("2. Acteurs et classification des données", h1),
        Paragraph("Le niveau de classification fixe les données auxquelles chaque organisation a accès. Une "
                  "organisation au statut « En attente » n'intervient pas avant la validation de son habilitation "
                  "par Acme Défense.", texte),
        Spacer(1, 0.4 * cm),
        tableau(ACTEURS, [3.4, 4.6, 2.8, 3.0, 2.2]),
        PageBreak(),
        Paragraph("3. Livrables et responsables", h1),
        Paragraph("Chaque livrable a un responsable, qui le rédige, et un relecteur, qui le valide avant sa "
                  "remise au comité de pilotage.", texte),
        Spacer(1, 0.4 * cm),
        tableau(LIVRABLES, [5.4, 2.0, 3.0, 3.0, 2.2]),
        Spacer(1, 0.6 * cm),
        Paragraph("4. Calendrier", h1),
        Paragraph("Le projet démarre en janvier 2027. Le comité de pilotage se réunit tous les deux mois ; les "
                  "échéances sont exprimées en mois après le démarrage.", texte),
    ]


def main():
    doc = SimpleDocTemplate(str(SORTIE), pagesize=A4, bottomMargin=2.5 * cm,
                            title="Projet Héron – Annexe C", author="Novaltis (fictif)")
    doc.build(contenu(), onFirstPage=pied_de_page, onLaterPages=pied_de_page)
    print(f"{SORTIE.name} : écrit")


if __name__ == "__main__":
    main()
