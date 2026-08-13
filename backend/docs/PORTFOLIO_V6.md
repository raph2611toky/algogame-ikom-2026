# portfolio_v6 — collaboration robuste et fin de partie sûre

`portfolio_v6` conserve la collaboration de `portfolio_v5` et corrige trois points critiques.

- Un coffre n'est plus marqué définitivement impossible à cause d'une position momentanée des machines. Seule l'impossibilité structurelle est mémorisée.
- Les machines utiles sont choisies en privilégiant une prise de contrôle rapide avant le coût global estimé, ce qui évite de poursuivre une machine automatique pendant des dizaines de ticks.
- Les pierres portées par une machine sont des objectifs explicites. Leur valeur est proportionnelle au nombre de pierres transportées et F/M peuvent les récupérer en partageant la même cellule avec la machine.

Ordre général : coffres directs en parallèle, déblocage spécialisé X/G, collecte secondaire pendant les déblocages, puis pierres libres et pierres transportées par les machines.

La stratégie ne termine plus par `STRATEGY_END_GAME` tant qu'un coffre structurellement réalisable ou des pierres encore présentes/transportées constituent un objectif productif, sauf blocage prolongé selon le seuil configuré.
