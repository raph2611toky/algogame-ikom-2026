# portfolio_v10 — opportunités partagées + micro-plans machines

`portfolio_v10` est une couche ciblée au-dessus de `portfolio_v9` / `portfolio_v8`.
Le but n'est pas de remplacer la logique principale qui fonctionne déjà, mais de
corriger les cartes où plusieurs coffres bloqués partagent des obstacles et où les
sous-plans de machines pouvaient se contredire d'un tick au suivant.

## Ce qui reste inchangé

Le cœur v8/v9 reste responsable de :

- la recherche des coffres directement poussables ;
- le parallélisme lorsque F et M ont deux coffres différents ;
- le relais stamina sur un même coffre ;
- la collecte des pierres libres et des pierres transportées par les machines ;
- le score par tick et `BEST_SCORE_END_GAME` ;
- les règles officielles de HACK, DIG, CUT, PUSH, buffer machine et stamina/batterie ;
- la protection courte avant UNHACK déjà présente dans v8.

## Garde-fou de non-régression

Pour les cartes jusqu'à **160 cellules** (ce qui couvre notamment 10×14), v10 délègue directement les décisions à l'instance `portfolio_v9` de référence. Cela garantit que l'amélioration destinée aux cartes complexes ne modifie pas les comportements déjà validés sur les petites cartes. Les ajouts ci-dessous sont activés sur les cartes plus grandes, comme la régression 15×20.

## Ajouts v10

### 1. Opportunités de déblocage partagées

Quand aucun coffre n'est directement accessible, v10 compare les obstacles des
coffres structurellement possibles. Un trou/arbre nécessaire à plusieurs coffres
obtient une priorité plus forte. Le classement considère :

- le nombre de coffres rendus directement accessibles après l'ouverture ;
- le nombre d'autres coffres partiellement préparés ;
- les obstacles communs ;
- une estimation du coût machine / déplacement / batterie.

Un coffre rendu direct vaut 600 unités internes (= 150 points × 4), ce qui garde
le classement cohérent avec la formule officielle du score.

### 2. Micro-plan machine engagé

Lorsqu'un planner choisit une séquence `HACK_CW / HACK_MOVE / ... / HACK_FILL`
ou `HACK_CUT`, cette courte séquence reste engagée tant que son état attendu est
valide. Un autre sous-planner ne peut plus annuler la rotation au tick suivant.

Le plan est invalidé si la position/orientation réelle diffère, si l'action devient
illégale, si la topologie utile change, ou si la batterie n'est plus suffisante.

### 3. Anti-oscillation

Une répétition `HACK_CW ↔ HACK_CCW` sur la même machine, même position et même
topologie est détectée. Le sous-plan est abandonné et la machine est brièvement
mise en cooldown de rotation afin de forcer un replan propre.

### 4. Deadlock X/G

Si les deux héros contrôlent des machines et attendent plusieurs ticks parce que
chaque machine bloque le partenaire, v10 tente une relocation courte et engagée
de la machine qui libère le plus vite la situation.

### 5. Protection globale des coffres contre les machines autonomes

La sécurité v8 à l'UNHACK est complétée par une prédiction bornée (24 décisions
automatiques) qui reproduit :

- rotations automatiques X=CCW / G=CW ;
- DIG automatique de X toutes les 5 avances ;
- CUT automatique du Grappler ;
- poussées de coffres.

Une poussée prévue dans un trou ou vers un bord non-cachette est classée critique.
Le héros compatible peut alors réserver un point d'interception sur la future
trajectoire de la machine, attendre en récupérant de la stamina, puis HACK au
passage. Pendant cette embuscade, l'autre héros conserve un micro-plan déjà engagé
ou collecte des pierres sans relancer tout le scheduler.

### 6. Cache structurel v10

Les profils de déblocage sont mémorisés tant que la topologie (coffres, trous,
arbres, rochers, cachettes) ne change pas. Un simple mouvement de F ou M ne relance
donc pas les gros planners structurels. Les plans directs restent, eux, évalués
sur l'état courant.

## Carte de régression 15×20

La carte `maps/regression/user_15x20_shared_opportunity.txt` est utilisée comme
régression pour les corridors partagés. Après le premier coffre, les deux coffres
du bas partagent notamment les obstacles centraux `(10,9)`, `(11,9)` et `(12,9)`.
Le test unitaire vérifie que v10 reconnaît cette opportunité commune.

Un run diagnostique local (non transformé en test de temps afin de ne pas rendre
la suite pytest fragile selon le CPU) a atteint au moins :

- 3 coffres sécurisés ;
- 7 pierres récupérées ;
- 0 coffre perdu ;

avant la poursuite du dernier corridor, alors que la trajectoire v9 fournie en
régression était ramenée par `BEST_SCORE_END_GAME` à 1 coffre / 3 pierres.

`BEST_SCORE_END_GAME` reste volontairement actif : il protège le score si une
trajectoire ultérieure devient moins rentable. V10 cherche à produire une meilleure
trajectoire, pas à supprimer ce filet de sécurité.
