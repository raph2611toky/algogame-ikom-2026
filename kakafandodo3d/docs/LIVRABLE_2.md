# Livrable 2 — Simulation dynamique

Ce livrable complète le rendu dynamique par le moteur temporel et les actions.

## Tick

- 1 tick = 1 seconde relative.
- affichage standard = 0,2 s réelles par tick (timescale 5).
- héros : MOVE/PUSH/HACK/WAIT = 1 tick ; HACK_MOVE déclenche un MOVE machine exécuté au tick suivant.
- machines : MOVE en deux phases `queued -> execute`; autres actions en un tick.

## Héros

- F : déplacement 4 directions, saute un seul trou, coût 10 stamina.
- M : déplacement 4 directions, franchit un seul arbre, coût 10 stamina.
- MOVE normal : -1 stamina.
- PUSH : -5 stamina si et seulement si le coffre est réellement déplacé.
- WAIT ou hacking/riding : +1 stamina toutes les 2 secondes relatives, max 100.
- HACK/HACK_* : -1 batterie par commande, batterie non rechargeable.
- F ne hacke que X ; M ne hacke que G.

## Machines

- X démarre LEFT, tourne CCW lorsqu'il est bloqué, MOVE en deux ticks, DIG après 5 pas automatiques.
- G démarre RIGHT, tourne CW lorsqu'il est bloqué, MOVE en deux ticks, entre sur `t` puis CUT au tick suivant.
- Deux machines ne partagent jamais une cellule.
- Les chaînes de machines synchronisées de même orientation peuvent avancer ensemble.
- Une machine derrière une voisine encore dans sa phase `pending MOVE` est considérée bloquée pour ce tick.

## Props

- `#` bloque tout.
- `t` bloque F/X/coffres ; M le franchit ; G le coupe.
- `o` bloque M/G ; F saute ; X traverse ; un coffre tombe et disparaît.
- `@` ne bloque rien ; un coffre poussé dessus est caché et retiré de la carte.
- `+` est récupéré automatiquement par tout agent. Les héros volent automatiquement les pierres portées par une machine lorsqu'ils partagent sa cellule.
- `*` peut être poussé. Des pushes opposés sur le même coffre annulent le déplacement.

## Test rapide

Dans l'écran Missions, charger :

`res://data/maps/tests/livrable2_showcase.txt`

Pour la référence officielle de 20 ticks, lancer :

`res://scenes/tests/GDDSampleSelfTest.tscn`

avec F6.
