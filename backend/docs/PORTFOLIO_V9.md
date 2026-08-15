# portfolio_v9 — relais stratégique de coffre

`portfolio_v9` étend `portfolio_v8`. Les règles du moteur ne changent pas : les coûts de stamina, les actions de hacking, les routines des machines, les buffers AlgoMada, la collecte des pierres et le score restent identiques.

## Problème corrigé

Dans v8, le changement de pousseur pouvait être réévalué presque à chaque nouvelle position du coffre. De plus, la signature de cache d'une route directe incluait la position du coffre lui-même : un PUSH normal pouvait donc être interprété comme un changement de topologie et forcer une replanification. Sur les longs trajets, cela favorisait des séquences F/M/F/M trop fréquentes.

## Politique v9

- Un seul héros est propriétaire/pousseur d'un coffre à un instant donné.
- Si le propriétaire peut terminer avec une marge de stamina, il garde le coffre.
- Sinon, le partenaire reçoit un point de relais futur calculé sur le plan de PUSH.
- Le partenaire rejoint ce point sans pousser puis WAIT afin de recharger sa stamina.
- Le relais se fait au point prévu, ou plus tôt si le pousseur n'a plus assez de stamina et que le partenaire possède une vraie réserve.
- Après un relais, on applique une hystérésis : l'ancien pousseur ne reprend pas immédiatement le même coffre avec seulement 5 stamina.
- Lorsque plusieurs coffres directs distincts existent, F et M gardent le parallélisme de v8 et peuvent pousser chacun leur coffre au même tick.
- Si le pousseur libéré est probablement requis pour un autre coffre (F pour des trous, M pour des arbres), le déblocage secondaire passe avant la préparation d'un nouveau relais.

## Cache de route

La signature d'une route v9 ignore uniquement le coffre suivi. Le déplacement attendu de ce coffre ne casse donc pas le cache. Les changements réellement dangereux continuent d'invalider le plan : trous ajoutés/supprimés, arbres coupés, autres coffres déplacés, rochers/cachettes différents.

## Régression synthétique

Carte longue à un coffre :

```text
1 30 300
F*.........................@.M
```

Dans l'environnement de test :

- `portfolio_v8` : 55 ticks, score 338.
- `portfolio_v9` : 26 ticks, score 352.
- v9 utilise un seul changement de pousseur sur le coffre : F pousse un segment, M se place au relais, puis M termine.

Ces chiffres servent uniquement de régression locale; le score officiel reste celui de l'évaluateur AlgoMada.
