# Décisions d’implémentation — GDD Twist 2 V3

Le GDD laisse volontairement certains choix au playtest. Le backend les centralise afin qu’ils puissent être modifiés sans toucher au frontend.

| Sujet | Décision v1.0 | Pourquoi |
|---|---|---|
| Temps | pas fixe de 100 ms | simultanéité reproductible et replay exact |
| KO | secours pendant 80 ticks, défaite immédiate si les deux sont KO | option coopérative recommandée par le GDD |
| Sortie | symbole additionnel `E`; les deux héros doivent être sur une sortie | matérialise « sortir ensemble » |
| Carte sans `E` | objectifs terminés = victoire | compatibilité avec les anciennes cartes |
| Saut assisté | héros porté, distance 2, montée max +4, descente max -4 | règle concrète, contrôlable et testable |
| Coffre récupéré | poussé dans `@` ou `E` | conserve le geste historique de sécurisation |
| Soin interrompu | charge remboursée | évite une perte opaque liée au réseau/animation |
| Machines autonomes | avancent ; X tourne à droite, G à gauche si bloqué | comportement déterministe conservant leurs fonctions |
| Télémétrie | score = `150C + 25P + floor(HP/4) + floor(T/2)` | comparaison de sessions uniquement, non officielle |

## Recommandations originales intégrées

1. **Ticks idempotents.** Chaque commande porte une `sequence`. Une retransmission réseau ne provoque jamais une deuxième action.
2. **Télégraphie équitable.** `guard.intended_destination`, le mode et les jauges de détection sont exposés au frontend pour rendre l’IA compréhensible.
3. **IA difficile à information partielle.** Après perte de vue, elle diffuse une probabilité sur les cases atteignables et retire les cases visuellement vérifiées vides. Elle ne lit pas la position cachée.
4. **Replay autoritaire.** `/replays` permet de reproduire un bug, un playtest ou une démonstration avec la même seed.

## À verrouiller avec l’équipe design

- conserver ou modifier les limites exactes d’altitude du saut assisté ;
- confirmer qu’un coffre est sécurisé dans un buisson et/ou une sortie ;
- confirmer que l’interruption d’un soin rembourse sa charge ;
- décider si une seule case `E` peut accueillir logiquement les deux héros ;
- décider si `telemetry_score` doit être affiché au joueur ou rester un outil de test.
