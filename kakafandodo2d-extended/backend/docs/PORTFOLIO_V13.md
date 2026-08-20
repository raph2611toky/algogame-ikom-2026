# Portfolio V13 — IA globale prédictive

Version backend : **0.13.0**

`portfolio_v13` ajoute une couche de décision au-dessus de V12 sans réécrire les mécaniques déjà validées. Le `Simulator` et `Rules` restent l'unique source de vérité pour l'exécution.

## Objectif

Maximiser le score officiel en raisonnant simultanément sur :

- coffre sécurisé : +150 points ;
- pierre : +25 points ;
- stamina restante ;
- batterie restante ;
- temps restant ;
- risques de perte/destruction des coffres ;
- contraintes asymétriques de l'élévation ;
- Look Ahead des machines, y compris au second tick d'un MOVE.

Pour comparer les coûts sans flottants, V13 raisonne en quarts de point :

```text
coffre sécurisé : +600 unités
pierre           : +100 unités
1 tick            :  -2 unités
1 stamina         :  -1 unité
1 batterie        :  -1 unité
```

Ainsi, une route légèrement plus longue peut être préférée si elle économise suffisamment de stamina/batterie.

## 1. Routes héros score-aware et dirigées

Le pathfinding utilise les transitions réelles de `hero_neighbors` :

- plat : 1 stamina ;
- montée +1/+2 : 3 stamina ;
- descente -1..-4 : 0 stamina ;
- montée >=3 : impossible ;
- descente >=5 : impossible ;
- saut de F / escalade de M : comparaison altitude départ -> landing et coût spécial 10.

Le graphe est donc dirigé : A -> B peut être légal alors que B -> A ne l'est pas.

## 2. Coffres

Les plans directs :

- n'envoient jamais volontairement un coffre vers une falaise >=5 ;
- respectent l'interdiction de pousser uphill pour F/M ;
- respectent arbres/coffres/machines ;
- acceptent `hole+bush` comme cachette, parce que le FAQ précise que DIG sur un bush ne détruit pas le bush ;
- en V13, évitent un PUSH immédiatement optimiste vers une case actuellement occupée par une machine. Les anciens planners gardent leur comportement pour compatibilité.

## 3. Estimation réelle des tâches machines

V13 ne classe plus les tâches critiques X/G par Manhattan. Il combine :

1. route score-aware du héros vers la machine ;
2. coût HACK ;
3. planner machine avec orientation/rotations ;
4. MOVE machine à 2 ticks ;
5. élévation ;
6. Look Ahead ;
7. batterie ;
8. récupération de stamina pendant le contrôle ;
9. pénalité si le chemin n'existe qu'en ignorant temporairement une autre machine.

Quand le héros contrôle déjà la machine, le micro-plan est aussi rejoué sur une copie de l'état avec le **Simulator de production**. Cela permet de repérer un Look Ahead qui deviendrait bloquant entre les deux ticks de HACK_MOVE.

## 4. Analyse globale d'un coffre

Pour chaque coffre viable, V13 évalue :

```text
coût déblocage trous/arbres
+ coût route finale coffre -> bush
- bonus obstacle partagé entre plusieurs objectifs
- bonus pierres récupérées sur la route
- bonus urgence si une machine autonome menace le coffre
```

Le coffre cible reste engagé tant que la topologie utile ne change pas afin d'éviter le ping-pong de décisions.

## 5. Prévision machines autonomes

La prédiction ne fige plus les autres machines. V13 clone l'état puis avance le vrai `Simulator` sur un horizon borné. Elle peut donc détecter :

- coffre poussé dans un trou ;
- coffre détruit par falaise >=5 ;
- coffre poussé vers une bordure non récupérable ;
- coffre fortement éloigné d'une cachette ;
- changement futur de Look Ahead produit par le mouvement d'une autre machine.

## 6. Collaboration F/M

V13 conserve les mécanismes déjà éprouvés :

- deux coffres traités en parallèle quand rentable ;
- relais de pousseur selon stamina ;
- séparation des rôles F/X et M/G ;
- micro-plans machines engagés ;
- protection des coffres ;
- anti-oscillation ;
- relocalisation ;
- deadlock resolver ;
- joint escape V12.

La différence est surtout dans la sélection : V13 compare les tâches selon leur coût réel de score et non leur proximité visuelle.

## 7. Portfolio final

Sur l'enveloppe d'évaluation (jusqu'à 160 cellules), le service exécute des candidats indépendants sous le même moteur :

- V13 `score` ;
- V13 `balanced` ;
- V13 `time` ;
- V12 ;
- V8.

Chaque trajectoire est ramenée à son meilleur préfixe de score légal, puis la meilleure est retenue selon : score, coffres sécurisés, pierres, coffres perdus, temps, ressources et nombre de ticks.

Cette approche protège contre une régression locale d'une nouvelle heuristique : une nouvelle idée ne gagne le portfolio que si son résultat simulé est réellement meilleur.

## 8. Grandes cartes

Au-dessus de 160 cellules, le profil V13 passe au planner borné `scalable_v1`. Les cartes cachées annoncées pour l'évaluation restent dans l'enveloppe où le portfolio complet est actif. Cette garde empêche les cartes utilisateur très grandes de provoquer une explosion combinatoire.

## 9. Arrêt propre

`OBJECTIVES_FINISHED` et `TIME_LIMIT` ont priorité sur les engagements internes. Un micro-plan machine mémorisé ne peut donc plus maintenir une mission déjà terminée jusqu'à la limite de temps.
