# portfolio_v9 — portfolio_v8 + relais minimal

Cette version corrige la première tentative `portfolio_v9` qui modifiait trop de décisions internes et pouvait régresser par rapport à `portfolio_v8`.

## Règle de conception

`portfolio_v9` garde **strictement le cœur de `portfolio_v8`**. Il n'override pas :

- le cache et la validation des routes (`_cache_route`, `_route_valid`) ;
- la sélection globale du coffre ;
- `_direct_collaborative_actions` ;
- le déblocage F/X et M/G ;
- la collecte des pierres libres ou portées par les machines ;
- la sécurité des machines avant UNHACK ;
- `next_actions` ;
- l'optimisation du meilleur préfixe de score.

Il ajoute seulement une couche de coopération sur **le héros qui pousse le même coffre**.

## Ajout 1 — affinité de pousseur

Après un PUSH, v8 peut replanifier et choisir l'autre héros pour le même coffre. V9 mémorise donc le pousseur du segment courant.

Si v8 sélectionne un **autre coffre**, sa décision est conservée telle quelle.

Si v8 sélectionne le **même coffre mais l'autre héros**, v9 autorise le relais seulement si :

- un petit segment a déjà été poussé ;
- le partenaire possède une réserve utile de stamina ;
- le pousseur courant est faible, ou le plan du partenaire apporte un gain runtime significatif ;
- ou le relais est nécessaire parce que le pousseur est à bout.

Cela évite surtout `F -> M -> F -> M` à chaque case sans changer les objectifs choisis par v8.

## Ajout 2 — dernier coffre et stamina très faible

Quand il ne reste qu'un seul coffre, le handoff interne de v8 est légèrement filtré : si le pousseur est à moins de 5 stamina mais que le partenaire n'a pas encore constitué une vraie réserve, il attend au lieu de transmettre immédiatement le coffre à un partenaire presque aussi vide.

Le partenaire recharge donc suffisamment pour pousser plusieurs cases avant un nouveau relais.

## Ajout 3 — staging facultatif

V8 possède déjà un mode où le héros libre fait `WAIT` pour conserver sa stamina en réserve d'un long coffre.

V9 ne remplace **que ce WAIT** : si le héros est déjà très bien rechargé, que le point de relais est proche (au maximum quelques ticks) et que le déplacement lui laisse une forte réserve, il peut rejoindre un point vers le milieu du trajet puis reprendre son `WAIT`.

Si ces conditions ne sont pas remplies, le WAIT original de v8 est conservé.

## Non-régression locale

- Sample officiel : v8 = v9 = score 382, 49 ticks.
- Régression 10x14 : v8 = v9 = score 633, 64 ticks.
- Deux coffres directs distincts : parallélisme F/M inchangé.
- Grande map 15x20 fournie par l'utilisateur :
  - v8 : score 1025, 361 ticks, 4 coffres, 9 pierres ;
  - v9 corrigé : score 1031, 349 ticks, 4 coffres, 9 pierres.

Ces mesures sont des tests locaux ; l'évaluateur AlgoMada reste la référence finale.
