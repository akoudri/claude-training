from lxml import etree

from obfuscation.formats.xml_texte import XML_SPACE, transformer_xml

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def transformer(xml, moteur, sens="obfusquer"):
    racine = etree.fromstring(xml.encode("utf-8"))
    transformer_xml(racine, moteur, sens)
    return racine


def textes(racine, ns, nom):
    return [e.text or "" for e in racine.iter(f"{{{ns}}}{nom}")]


def test_paragraphe_word_coupe_et_espaces_preserves(moteur):
    racine = transformer(
        f'<w:document xmlns:w="{W}"><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Nova</w:t></w:r>'
        f"<w:r><w:t>ltis SA et</w:t></w:r></w:p></w:document>",
        moteur,
    )
    assert textes(racine, W, "t") == ["[CLIENT_1]", " et"]
    assert list(racine.iter(f"{{{W}}}t"))[1].get(XML_SPACE) == "preserve"


def test_revision_supprimee_traitee(moteur):
    racine = transformer(
        f'<w:document xmlns:w="{W}"><w:p><w:del w:author="Jeanne Martin"><w:r><w:delText>Novaltis</w:delText>'
        f"</w:r></w:del></w:p></w:document>",
        moteur,
    )
    assert textes(racine, W, "delText") == ["[CLIENT_1]"]
    assert next(racine.iter(f"{{{W}}}del")).get(f"{{{W}}}author") == "[PERSONNE_1]"


def test_paragraphes_imbriques_non_fusionnes(moteur):
    # « Nova » (paragraphe externe) et « ltis » (zone de texte) ne forment pas un mot.
    racine = transformer(
        f'<w:document xmlns:w="{W}"><w:p><w:r><w:t>Nova</w:t></w:r><w:r><w:txbxContent><w:p><w:r>'
        f"<w:t>ltis</w:t></w:r></w:p></w:txbxContent></w:r></w:p></w:document>",
        moteur,
    )
    assert textes(racine, W, "t") == ["Nova", "ltis"]


def test_chaines_partagees_texte_enrichi(moteur):
    racine = transformer(
        f'<sst xmlns="{X}"><si><r><t>Nova</t></r><r><rPr><b/></rPr><t>ltis</t></r></si><si><t>Héron</t></si></sst>',
        moteur,
    )
    assert textes(racine, X, "t") == ["[CLIENT_1]", "", "[PROJET_1]"]


def test_metadonnees_et_attributs(moteur):
    racine = transformer(
        f'<racine xmlns:w="{W}" xmlns:wp="{WP}" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:creator>Jeanne Martin</dc:creator>"
        f'<w:comment w:author="Jeanne Martin" w:initials="JM"/>'
        f'<wp:docPr id="1" name="Logo Novaltis" descr="Logo de Novaltis"/></racine>',
        moteur,
    )
    assert textes(racine, "http://purl.org/dc/elements/1.1/", "creator") == ["[PERSONNE_1]"]
    doc_pr = next(racine.iter(f"{{{WP}}}docPr"))
    assert (doc_pr.get("name"), doc_pr.get("descr")) == ("Logo [CLIENT_1]", "Logo de [CLIENT_1]")


def test_seuls_les_liens_externes_sont_traites(moteur):
    racine = transformer(
        f'<Relationships xmlns="{REL}">'
        f'<Relationship Id="rId1" Type="h" Target="mailto:jeanne.martin@novaltis.example" TargetMode="External"/>'
        f'<Relationship Id="rId2" Type="i" Target="media/novaltis.png"/></Relationships>',
        moteur,
    )
    cibles = [r.get("Target") for r in racine.iter(f"{{{REL}}}Relationship")]
    assert cibles == ["mailto:[EMAIL_1]", "media/novaltis.png"]


def test_cellules(moteur):
    racine = transformer(
        f'<worksheet xmlns="{X}"><sheetData><row r="1">'
        f'<c r="A1" t="s"><v>123456782</v></c>'
        f'<c r="B1" t="str"><f>A1</f><v>Novaltis</v></c>'
        f'<c r="C1"><v>123456782</v></c>'
        f'<c r="D1"><v>42</v></c>'
        f"</row></sheetData></worksheet>",
        moteur,
    )
    cellules = {c.get("r"): c for c in racine.iter(f"{{{X}}}c")}
    assert cellules["A1"].findtext(f"{{{X}}}v") == "123456782"  # index de chaîne partagée : intact
    assert cellules["B1"].findtext(f"{{{X}}}v") == "[CLIENT_1]"  # résultat texte d'une formule
    assert cellules["C1"].get("t") == "inlineStr"
    assert cellules["C1"].findtext(f"{{{X}}}is/{{{X}}}t") == "[SIREN_1]"
    assert cellules["D1"].findtext(f"{{{X}}}v") == "42"


def test_caches_de_graphique(moteur):
    racine = transformer(
        f'<c:chartSpace xmlns:c="{C}"><c:strCache><c:pt idx="0"><c:v>Novaltis</c:v></c:pt></c:strCache>'
        f'<c:numCache><c:pt idx="0"><c:v>123456782</c:v></c:pt></c:numCache></c:chartSpace>',
        moteur,
    )
    assert textes(racine, C, "v") == ["[CLIENT_1]", "123456782"]


def test_noms_de_feuilles_et_formules(moteur):
    racine = transformer(
        f'<workbook xmlns="{X}"><sheets><sheet name="Novaltis SA" sheetId="1"/><sheet name="Budget Héron" sheetId="2"/>'
        f"</sheets><definedNames><definedName name=\"Zone\">'Novaltis SA'!$A$1</definedName></definedNames>"
        f'<f>SUM(Novaltis!A1:A3)&amp;"Novaltis"</f></workbook>',
        moteur,
    )
    assert [s.get("name") for s in racine.iter(f"{{{X}}}sheet")] == ["CLIENT_1", "Budget PROJET_1"]
    assert textes(racine, X, "definedName") == ["'CLIENT_1'!$A$1"]
    assert textes(racine, X, "f") == ['SUM(CLIENT_1!A1:A3)&"[CLIENT_1]"']


def test_formules_restaurees_avec_guillemets_si_besoin(moteur):
    moteur.transformer("Projet Héron, Jeanne Martin", "obfusquer")
    racine = transformer(
        f"<worksheet xmlns=\"{X}\"><f>'Budget PROJET_1'!A1&amp;PERSONNE_1!B2</f></worksheet>", moteur, "restaurer"
    )
    assert textes(racine, X, "f") == ["'Budget Projet Héron'!A1&'Jeanne Martin'!B2"]


def test_nom_de_feuille_invalide_a_la_restauration(moteur):
    moteur.transformer("https://intranet.novaltis.fr/a", "obfusquer")
    racine = transformer(f'<workbook xmlns="{X}"><sheets><sheet name="URL_1"/></sheets></workbook>', moteur, "restaurer")
    assert next(racine.iter(f"{{{X}}}sheet")).get("name") == "URL_1"
    assert any("URL_1" in a for a in moteur.avertissements)


def test_en_tete_excel_avec_codes(moteur):
    racine = transformer(
        f'<worksheet xmlns="{X}"><headerFooter><oddHeader>&amp;CNovaltis &amp;"Arial,Gras"Héron</oddHeader>'
        f"</headerFooter></worksheet>",
        moteur,
    )
    assert textes(racine, X, "oddHeader") == ['&C[CLIENT_1] &"Arial,Gras"[PROJET_1]']


def test_valeur_numerique_en_cache_d_une_formule_retiree(moteur):
    # Le résultat mis en cache d'une formule (ici un SIRET) serait lisible dans le fichier.
    racine = transformer(
        f'<worksheet xmlns="{X}"><sheetData><row r="1"><c r="E1"><f>A2</f><v>12345678200010</v></c>'
        f'<c r="F1"><f>A3</f><v>42</v></c></row></sheetData></worksheet>',
        moteur,
    )
    cellules = {c.get("r"): c for c in racine.iter(f"{{{X}}}c")}
    assert cellules["E1"].find(f"{{{X}}}v") is None and cellules["E1"].findtext(f"{{{X}}}f") == "A2"
    assert cellules["F1"].findtext(f"{{{X}}}v") == "42"


def test_instructions_de_champ_et_alias(moteur):
    racine = transformer(
        f'<w:document xmlns:w="{W}"><w:p><w:fldSimple w:instr="HYPERLINK &quot;https://novaltis.fr&quot;"/></w:p>'
        f'<w:sdt><w:sdtPr><w:alias w:val="Contrat Novaltis"/></w:sdtPr></w:sdt></w:document>',
        moteur,
    )
    assert next(racine.iter(f"{{{W}}}fldSimple")).get(f"{{{W}}}instr") == 'HYPERLINK "[URL_1]"'
    assert next(racine.iter(f"{{{W}}}alias")).get(f"{{{W}}}val") == "Contrat [CLIENT_1]"


def test_tabulation_dans_un_terme(moteur):
    racine = transformer(
        f'<w:document xmlns:w="{W}"><w:p><w:r><w:t>Jeanne</w:t><w:tab/><w:t>Martin signe</w:t></w:r></w:p></w:document>',
        moteur,
    )
    assert textes(racine, W, "t") == ["[PERSONNE_1]", " signe"]
    assert next(racine.iter(f"{{{W}}}tab"), None) is None


def test_tableaux_et_tableaux_croises_excel(moteur):
    racine = transformer(
        f'<r xmlns="{X}"><tableColumn id="1" name="Budget Novaltis"/><worksheetSource ref="A1:B3" sheet="Novaltis"/>'
        f'<cacheField name="Client Novaltis"><sharedItems><s v="Novaltis SA"/></sharedItems></cacheField></r>',
        moteur,
    )
    assert next(racine.iter(f"{{{X}}}tableColumn")).get("name") == "Budget [CLIENT_1]"
    assert next(racine.iter(f"{{{X}}}worksheetSource")).get("sheet") == "CLIENT_1"
    assert next(racine.iter(f"{{{X}}}cacheField")).get("name") == "Client [CLIENT_1]"
    assert next(racine.iter(f"{{{X}}}s")).get("v") == "[CLIENT_1]"


def test_nom_de_feuille_trop_long_remplace_entierement(moteur):
    nom = "Budget de J. Martin 2026–2030 v"  # 31 caractères, le maximum d'Excel ; PERSONNE_1 l'allonge
    racine = transformer(f'<workbook xmlns="{X}"><sheets><sheet name="{nom}"/></sheets><f>\'{nom}\'!A1</f></workbook>', moteur)
    feuille = next(racine.iter(f"{{{X}}}sheet")).get("name")
    assert feuille == "FEUILLE_1" and textes(racine, X, "f") == ["'FEUILLE_1'!A1"]
    assert moteur.transformer(feuille, "restaurer") == nom
