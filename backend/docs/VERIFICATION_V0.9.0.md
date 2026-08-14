# Vérification v0.9.0 / portfolio_v8

## Carte officielle 5x7

Résultat observé :

```text
score              382
pierres             5
coffres sécurisés   1
coffres perdus      0
ticks               49
OBJECTIVES_FINISHED
```

## Régression 15x20 / 700

Carte : `maps/regression/user_15x20_portfolio_v8.txt`.

Résultat observé dans l'environnement de vérification :

```text
score              1025
pierres             9 / 9
coffres sécurisés   4 / 4
coffres perdus      0
ticks               361
remaining_time      339
total_stamina       2
total_battery       125
OBJECTIVES_FINISHED
```

Temps de calcul observé : environ 29 à 32 secondes selon le run. Cette mesure dépend du processeur.

La correction déterminante sur cette carte est l'invalidation d'une route coffre lorsqu'une machine crée un nouveau trou après le calcul initial du plan. Sans cette invalidation, le pousseur pouvait conserver une suite de `PUSH_*` devenue impossible et attendre jusqu'au `TIME_LIMIT`.

## Tests

87 tests sont collectés. Ils couvrent les règles, buffers staff, parser, score, replay, pierres portées par les machines, Swagger, jobs asynchrones, catalogue de stratégies et les protections v8.
