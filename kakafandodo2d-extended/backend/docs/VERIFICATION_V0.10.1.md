# Vérification v0.10.1 — portfolio_v9 minimal

Objectif: corriger la regression de la première v9 en gardant strictement portfolio_v8 comme coeur.

Résultats locaux:

- sample officiel: v8 = v9 = 382 points / 49 ticks / 1 coffre / 5 pierres.
- user 10x14: v8 = v9 = 633 points / 64 ticks / 2 coffres / 6 pierres.
- grande 15x20: v8 = 1025 / 361 ticks; v9 = 1031 / 349 ticks; 4 coffres / 9 pierres / 0 perdu.
- long coffre synthétique: v9 réduit les changements de pousseur et ne perd pas de score.
- deux coffres directs: les deux héros continuent à pousser en parallèle des coffres distincts.

Le test `test_v9_is_a_thin_v8_layer_not_a_replacement` vérifie que v9 ne réimplémente pas les méthodes coeur de v8.
