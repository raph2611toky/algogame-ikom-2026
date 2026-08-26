from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


BLACK = colors.black
WHITE = colors.white


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = A4
    margin = 13 * mm
    doc = BaseDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=13 * mm,
        bottomMargin=12 * mm,
        title="KAKAFANDODO — Documentation backend Co-player",
        author="Équipe KAKAFANDODO",
        subject="Architecture, workflow et endpoints du backend Twist 2",
    )

    def decorate(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(BLACK)
        canvas.setLineWidth(0.55)
        canvas.line(margin, 9 * mm, width - margin, 9 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(margin, 5.6 * mm, "KAKAFANDODO — Backend Co-player v1.0")
        canvas.drawRightString(width - margin, 5.6 * mm, f"{document.page} / 2")
        canvas.restoreState()

    frame = Frame(margin, 12 * mm, width - 2 * margin, height - 25 * mm, id="main")
    doc.addPageTemplates(PageTemplate(id="bw", frames=[frame], onPage=decorate))

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleBW",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=22,
        textColor=BLACK,
        alignment=TA_LEFT,
        spaceAfter=2 * mm,
    )
    subtitle = ParagraphStyle(
        "SubtitleBW",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=BLACK,
        spaceAfter=3 * mm,
    )
    h2 = ParagraphStyle(
        "H2BW",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11.2,
        leading=13,
        textColor=BLACK,
        spaceBefore=2.2 * mm,
        spaceAfter=1.2 * mm,
    )
    body = ParagraphStyle(
        "BodyBW",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.1,
        leading=10.4,
        textColor=BLACK,
        spaceAfter=1.1 * mm,
    )
    small = ParagraphStyle(
        "SmallBW",
        parent=body,
        fontSize=7.35,
        leading=9.0,
        spaceAfter=0,
    )
    tiny = ParagraphStyle(
        "TinyBW",
        parent=body,
        fontSize=6.7,
        leading=8.0,
        spaceAfter=0,
    )
    code = ParagraphStyle(
        "CodeBW",
        parent=body,
        fontName="Courier",
        fontSize=6.55,
        leading=8.0,
        leftIndent=2.2 * mm,
        rightIndent=2.2 * mm,
        borderColor=BLACK,
        borderWidth=0.55,
        borderPadding=2.0 * mm,
        spaceBefore=1 * mm,
        spaceAfter=1.5 * mm,
    )
    label = ParagraphStyle(
        "LabelBW",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8.5,
        textColor=WHITE,
        backColor=BLACK,
        borderPadding=1.3 * mm,
        alignment=TA_CENTER,
        spaceAfter=1.3 * mm,
    )

    def table(data, widths, *, header=True, font=7.0, padding=3.0):
        result = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands = [
            ("BOX", (0, 0), (-1, -1), 0.55, BLACK),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, BLACK),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), padding),
            ("RIGHTPADDING", (0, 0), (-1, -1), padding),
            ("TOPPADDING", (0, 0), (-1, -1), padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), font),
            ("TEXTCOLOR", (0, 0), (-1, -1), BLACK),
        ]
        if header:
            commands += [
                ("BACKGROUND", (0, 0), (-1, 0), BLACK),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        result.setStyle(TableStyle(commands))
        return result

    story = []
    story += [
        paragraph("BACKEND CO-PLAYER", title),
        paragraph(
            "KAKAFANDODO — Twist 2 · FastAPI autoritaire · moteur déterministe à ticks de 100 ms",
            subtitle,
        ),
        paragraph(
            "Le frontend envoie les <b>intentions</b> des deux joueurs. Le backend décide l’état réel : collisions, relief, HP, stamina, soin, portage, objectifs, bruit, machines et gardien. Le frontend anime uniquement les événements validés.",
            body,
        ),
        paragraph("1 — Architecture : quoi fait quoi", h2),
    ]

    architecture = [
        ["Couche / chemin", "Responsabilité", "Entrée → sortie"],
        [paragraph("<b>api/routes</b>", small), paragraph("REST, WebSocket, santé, contrats et erreurs HTTP.", small), paragraph("JSON client → schémas", small)],
        [paragraph("<b>schemas</b>", small), paragraph("Validation Pydantic stricte des cartes, commandes et réponses.", small), paragraph("payload → types sûrs", small)],
        [paragraph("<b>services/game_service.py</b>", small), paragraph("Sessions mémoire, verrou, reset, replay et ticks idempotents.", small), paragraph("sequence N → snapshot N", small)],
        [paragraph("<b>engine/simulator.py</b>", small), paragraph("Arbitre : résout deux actions simultanées et avance le monde.", small), paragraph("état + F/M → état + événements", small)],
        [paragraph("<b>engine/perception.py</b>", small), paragraph("Vision, occlusion, détection, bruits et mémoire du gardien.", small), paragraph("observations → mode/mémoire", small)],
        [paragraph("<b>engine/guard_ai</b>", small), paragraph("Trois politiques interchangeables ; aucune n’altère les règles.", small), paragraph("mémoire → direction", small)],
        [paragraph("<b>domain</b>", small), paragraph("État métier : héros, garde, machines, terrain, événements.", small), paragraph("source de vérité typée", small)],
    ]
    story += [table(architecture, [40 * mm, 91 * mm, 37 * mm], font=6.9), Spacer(1, 1.2 * mm)]

    story += [paragraph("Ordre d’un tick autoritaire", h2)]
    tick_flow = [[paragraph(f"<b>{i}</b><br/>{text}", tiny) for i, text in enumerate([
        "Timers", "Soins", "F + M", "Collecte", "Machines", "Perception + IA", "Dégâts + fin"
    ], start=1)]]
    story += [table(tick_flow, [24 * mm] * 7, header=False, font=6.7, padding=3.5)]

    story += [paragraph("IA du gardien", h2)]
    ai_table = [
        ["Niveau", "Décision", "Robustesse / équité"],
        [paragraph("<b>Facile</b>", small), paragraph("WAIT ou mouvement légal pseudo-aléatoire, seed reproductible.", small), paragraph("Prévisible statistiquement ; aucune triche.", small)],
        [paragraph("<b>Moyen</b>", small), paragraph("Vue → dernière position → bruit → patrouille ; chemin A*.", small), paragraph("Bonne pression, anticipation limitée.", small)],
        [paragraph("<b>Difficile</b>", small), paragraph("Cible tactique + A* + carte probabiliste après perte de vue.", small), paragraph("N’utilise jamais la position réelle d’un héros invisible.", small)],
    ]
    story += [table(ai_table, [25 * mm, 84 * mm, 59 * mm], font=6.9)]

    story += [paragraph("Règles GDD couvertes", h2)]
    rules_left = paragraph(
        "• Actions simultanées et WAIT non bloquant<br/>• HP → vitesse (100/90/75/55 %)<br/>• pierre = objectif permanent + 1 charge<br/>• soin personnel/partenaire interruptible<br/>• portage réciproque et saut assisté validé",
        small,
    )
    rules_right = paragraph(
        "• cône de vision, occlusion, bruit, mémoire<br/>• garde 80/100/120 %, impact −20 HP<br/>• F franchit un trou ; M franchit un arbre<br/>• machines rapides et très bruyantes<br/>• objectifs puis sortie des deux héros",
        small,
    )
    story += [table([[rules_left, rules_right]], [84 * mm, 84 * mm], header=False, font=7.0, padding=5.0)]

    story += [paragraph("CHOIX EXPLICITES AJOUTÉS", label)]
    story += [paragraph(
        "<b>Original et utile :</b> ticks numérotés/idempotents (anti-double action réseau), intention du gardien exposée pour une télégraphie juste, replay autoritaire pour reproduire les bugs. Points GDD non verrouillés : sortie <b>E</b> optionnelle, secours KO 8 s, saut assisté de 2 cases. Toutes ces valeurs sont centralisées et configurables.",
        small,
    )]

    story += [PageBreak()]
    story += [
        paragraph("UTILISER LE BACKEND", title),
        paragraph("Démarrage, workflow temps réel, endpoints et exemples minimaux", subtitle),
        paragraph("1 — Installer et lancer", h2),
        paragraph(
            "python3 -m venv .venv<br/>source .venv/bin/activate<br/>python3 -m pip install -e '.[test]'<br/>uvicorn app.main:app --reload",
            code,
        ),
    ]

    story += [paragraph("2 — Workflow frontend", h2)]
    workflow = [
        ["Étape", "Appel", "Résultat attendu"],
        ["1", "POST /maps/validate", "Valider map.txt et elevation.txt avant l’écran de jeu."],
        ["2", "POST /games", "Recevoir game_id et snapshot initial (sequence 0)."],
        ["3", "POST /games/{id}/ticks", "Envoyer F et M avec sequence 1, 2, 3…"],
        ["4", "Animer events[]", "Ne déplacer visuellement que ce que le backend confirme."],
        ["5", "GET /games/{id} / reset / delete", "Resynchroniser, recommencer ou libérer la session."],
    ]
    story += [table(workflow, [13 * mm, 56 * mm, 99 * mm], font=6.85, padding=3.0)]

    story += [paragraph("3 — Endpoints", h2)]
    endpoints = [
        ["Méthode", "Route", "Usage"],
        ["GET", "/api/v1/health", "état du service"],
        ["GET", "/api/v1/contracts", "symboles, actions, IA"],
        ["POST", "/api/v1/maps/validate", "contrôle sans session"],
        ["POST", "/api/v1/games", "création"],
        ["GET", "/api/v1/games/{id}", "snapshot courant"],
        ["POST", "/api/v1/games/{id}/ticks", "transition autoritaire"],
        ["POST", "/api/v1/games/{id}/reset", "retour état initial"],
        ["DELETE", "/api/v1/games/{id}", "fin de session"],
        ["POST", "/api/v1/replays", "rejeu hors temps réel"],
        ["WS", "/api/v1/games/{id}/ws", "boucle bidirectionnelle"],
    ]
    story += [table(endpoints, [20 * mm, 77 * mm, 71 * mm], font=6.65, padding=2.3)]

    story += [paragraph("4 — Exemples JSON", h2)]
    examples = Table(
        [
            [paragraph("<b>Créer</b>", small), paragraph("<b>Tick simultané</b>", small)],
            [
                paragraph(
                    '{<br/>"map_text": "5 7 120\\n…",<br/>"elevation_text": null,<br/>"difficulty": "hard",<br/>"seed": 42<br/>}',
                    code,
                ),
                paragraph(
                    '{<br/>"sequence": 1,<br/>"actions": {<br/> "F": {"action":"RUN", "direction":"RIGHT"},<br/> "M": {"action":"WAIT"}<br/>}<br/>}',
                    code,
                ),
            ],
        ],
        colWidths=[84 * mm, 84 * mm],
    )
    examples.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2 * mm),
        ("TOPPADDING", (0, 1), (-1, 1), 1 * mm),
    ]))
    story += [examples]

    story += [paragraph("Réponse à consommer", h2)]
    story += [paragraph(
        "<b>status</b>, <b>heroes</b>, <b>guard</b>, <b>machines</b>, <b>objectives</b>, <b>map</b>, <b>events[]</b>, <b>remaining_seconds</b>. Une retransmission de la même sequence renvoie <b>duplicate: true</b> sans rejouer l’action ; un trou de séquence renvoie HTTP 409. Swagger complet : <b>/docs</b>.",
        small,
    )]
    story += [paragraph(
        "NOTE — telemetry_score sert aux comparaisons de playtests ; il n’est pas déclaré comme score officiel du Twist 2. Les arbitrages de design sont listés dans docs/GDD_DECISIONS.md.",
        label,
    )]

    doc.build(story)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/backend_documentation.pdf")
    build(target.resolve())
