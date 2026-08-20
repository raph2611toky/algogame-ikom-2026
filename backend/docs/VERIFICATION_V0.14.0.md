# Vérification v0.14.0 — Global Mission / Machine Chest

## Changements critiques vérifiés

- `portfolio_v14` devient la stratégie par défaut ;
- suppression du gate « plus de 8 pierres => pierres uniquement » dans le fallback scalable ;
- ajout du `MachineChestPlanner` pour les coffres nécessitant une poussée uphill de machine ;
- allocation conjointe F/M ;
- réserve de stamina non linéaire ;
- tracking d'un coffre mobile pendant les poussées ;
- réservation dynamique coffre/machine entre les héros ;
- revalidation live de `HACK_MOVE` ;
- interception bornée des machines autonomes ;
- release sûr d'une machine avant abandon ;
- V14 actif sur les cartes 161..400 cellules au lieu du fallback immédiat V13 -> scalable.

## Régression 15x20

Fichiers :

```text
maps/regression/v14_complex_15x20.txt
maps/regression/v14_complex_15x20_elevation.txt
```

Commande :

```bash
python scripts/benchmark_v14.py
```

Résultat déterministe observé avec le moteur local courant :

```text
score=1214
ticks=176 remaining=324
chests=5 lost=0
stones=10
stamina=122 battery=86
end_reason=OBJECTIVES_FINISHED
```

Le résultat V13/scalable fourni avant V14 sur la même carte était : score 818, 2 coffres sécurisés sur 5, 10 pierres, 0 coffre perdu, stamina totale 7 et batterie totale 200. Le benchmark montre donc que la batterie est maintenant utilisée lorsque rentable et que les trois coffres qui demandaient une logique machine ne sont plus abandonnés.

## Tests unitaires dédiés

`tests/test_strategy_v14.py` couvre notamment :

1. un coffre `1 -> 2` en altitude qu'un héros ne peut pas pousser mais qu'un Grappler hacké peut sécuriser ;
2. deux coffres indépendants, afin de vérifier que F et M contribuent tous les deux à l'exécution.

## Important

Ces scores sont ceux du `Simulator` local. Le fichier `actions.txt` doit toujours être validé avec le Game Runner officiel AlgoMada dès que son contrat Java est disponible. `scripts/differential_runner.py` reste fourni pour cette comparaison.
