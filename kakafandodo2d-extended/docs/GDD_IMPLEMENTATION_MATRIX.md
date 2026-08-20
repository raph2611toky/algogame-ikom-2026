# Kakafandodo — matrice d'implémentation du GDD

Ce document indique où chaque règle importante du Gameplay Design Document AlgoGames 2 est prise en charge.

## Flux principal

- `StartScreen.tscn` : splash + COMMENCER.
- `MainMenu.tscn` : JOUER / MISSIONS / PARAMÈTRES / CRÉDITS / QUITTER.
- `MissionSelect.tscn` : import d'un `map.txt`, validation et aperçu dynamique.
- `GameScreen.tscn` : Zero Player Game, carte dynamique, HUD, lecture/pause/vitesse d'observation.
- `ResultScreen.tscn` : score, détails et emplacement de `actions.txt`.

## Fichier map

Implémenté dans `scripts/game/map_loader.gd`.

Format accepté :

```text
H W TEMPS
<ligne 1 de W caractères>
...
<ligne H de W caractères>
```

Symboles :

- `.` vide
- `F` Ikotofosa
- `M` Imahaki
- `#` roche
- `t` arbre
- `o` trou
- `X` excavateur
- `G` grappler
- `*` coffre
- `+` pierre précieuse
- `@` cache/buisson

Le parseur refuse les dimensions incorrectes, les symboles inconnus et les cartes ne contenant pas exactement un `F` et un `M`.

## Etat du monde

`scripts/game/game_state.gd`

- origine logique : coin supérieur gauche ; positions internes `Vector2i(x, y)` ; HUD affiché en `(ligne, colonne)` = `(y, x)` comme dans l'annexe du GDD ;
- stamina F/M : 100 maximum ;
- batterie F/M : 100, non rechargeable ;
- orientation initiale X : LEFT ;
- orientation initiale G : RIGHT ;
- compteur de pas excavateur ;
- MOVE machine en attente ;
- hacking et délai de reprise automatique ;
- pierres portées par les machines ;
- coffres cachés/perdus ;
- score final.

## Déplacements héros

`scripts/game/simulation_engine.gd` → `_hero_transition()` et `_prepare_hero_action()`.

- UP / DOWN / LEFT / RIGHT : 1 stamina ;
- Ikotofosa : saute exactement un trou, coût 10 ; deux trous successifs sont invalides ;
- Imahaki : franchit exactement un arbre, coût 10 ; deux arbres successifs sont invalides ;
- roche : bloque les deux ;
- arbre : bloque F ;
- trou : bloque M ;
- action invalide : convertie en WAIT ;
- les héros peuvent partager une cellule avec un autre agent ou un coffre conformément aux exemples du GDD.

## Coffres

`scripts/game/simulation_engine.gd` → `_resolve_chest_pushes()`.

- PUSH_UP / DOWN / LEFT / RIGHT : 5 stamina si le push aboutit ;
- un coffre ne peut pas pousser un coffre voisin ;
- plusieurs agents poussant le même coffre dans des directions différentes : échec ;
- plusieurs agents poussant dans la même direction : autorisé ;
- trou : coffre supprimé et compté perdu ;
- buisson : coffre supprimé de la grille et compté caché ;
- roche/arbre/autre coffre : blocage ;
- destination de coffre réservée pendant le tick pour éviter qu'une autre machine n'y entre simultanément.

## Pierres

`scripts/game/game_state.gd`.

- ramassage automatique par F/M/X/G ;
- une machine conserve les pierres ramassées ;
- F/M récupèrent automatiquement toutes les pierres d'une machine lorsqu'ils partagent sa cellule ;
- les pierres sécurisées par les héros ne sont pas perdues.

## Hacking

`scripts/game/simulation_engine.gd`.

- `HACK` uniquement en partageant la cellule de la machine compatible ;
- F pilote X ; M pilote G ;
- `HACK`, `HACK_MOVE`, `HACK_CW`, `HACK_CCW`, `HACK_FILL`, `HACK_CUT` consomment chacun 1 batterie lorsqu'ils sont valides ;
- batterie 0 : hacking impossible ;
- `HACK_MOVE` prend deux ticks via `pending_move` ; le tick d'exécution force le héros à WAIT et le transporte avec la machine ;
- déplacement du héros hors de la machine : UNHACK puis un tick de délai avant reprise automatique ;
- X : `HACK_FILL` remplit le trou devant lui ;
- G : lorsqu'il est sur un arbre, WAIT permet la coupe ; `HACK_CUT` est aussi pris en charge explicitement.

## Machines automatiques

`scripts/game/simulation_engine.gd`.

### Excavateur X

- avance dans son orientation ;
- MOVE = deux ticks ;
- bloqué : rotation CCW ;
- après cinq déplacements exécutés : DIG pendant un tick ;
- peut entrer sur un trou ;
- arbre/roche : bloque.

### Grappler G

- avance dans son orientation ;
- MOVE = deux ticks ;
- bloqué : rotation CW ;
- arrive sur un arbre, puis le coupe automatiquement pendant un tick ;
- trou/roche : bloque.

### Plusieurs machines

Le moteur résout les mouvements en deux phases et empêche deux machines d'occuper la même case.

- des machines adjacentes synchronisées et allant dans la même direction peuvent avancer comme une chaîne ;
- si une machine devant est encore dans une phase MOVE différente au début du tick, la machine derrière ne profite pas artificiellement de la case libérée dans ce même tick : elle considère le chemin bloqué et applique sa rotation automatique ;
- deux machines ciblant la même case sont bloquées ;
- une destination réservée par un coffre poussé est prioritaire afin d'éviter une superposition coffre/machine.

Les deux derniers points sont des règles de résolution déterministes nécessaires aux conflits simultanés ; si une clarification officielle AlgoMada impose une priorité différente, elles sont isolées dans `simulation_engine.gd` et peuvent être changées sans toucher au rendu ni au solveur.

## Temps

- un tick = 1 seconde relative ;
- visualisation standard : 0,2 seconde réelle par tick (timescale 5) ;
- mouvement héros : un tick ;
- MOVE machine / HACK_MOVE : deux ticks ;
- autres actions machines/hacking : un tick ;
- récupération stamina : +1 tous les deux ticks de WAIT/hacking, maximum 100 ;
- les boutons x1/x2/x4 changent seulement la vitesse d'observation, jamais le contenu des ticks ni le fichier de sortie.

## actions.txt

`scripts/io/actions_writer.gd`.

Chaque tick ajoute :

```text
ACTION_F | ACTION_M
```

Puis la dernière ligne est :

```text
END_GAME
```

Le fichier est écrit dans `user://actions.txt`. L'écran de résultat affiche son chemin système et peut ouvrir son dossier.

## Score

`scripts/game/game_state.gd` :

```text
R = C*150 + P*25 + (S+B)/4 + T/2
```

Les divisions sont des divisions entières car les opérandes sont des `int` en GDScript.

## Rendu 2D dynamique

`scripts/game/game_board.gd` et `entity_view.gd`.

La carte n'est pas une image fixe. Sa taille est calculée à partir de H/W et de l'espace disponible. Terrain et objets sont dessinés à partir de l'état courant :

- sol par cellule ;
- roches ;
- arbres ;
- trous ;
- buissons ;
- pierres ;
- F/M ;
- X/G avec orientation ;
- coffres ;
- compteur de coffres cachés dans chaque buisson.

Les mouvements, sauts/franchissements et suppressions de coffres sont animés avec des Tweens.

## Solveur

`scripts/ai/demo_brain.gd` est volontairement un **baseline fonctionnel**, pas l'algorithme compétitif final. Le moteur appelle uniquement :

```gdscript
brain.get_actions(state)
```

On peut remplacer `DemoBrain` par A*, Dijkstra, Beam Search, MCTS, GOAP, etc., sans modifier le parser, les règles, l'interface ou l'export.

## GDD Addendum — elevation.txt / 2D Extended

La version `kakafandodo2d-extended` ajoute la matrice d'élévation au contrat frontend/backend.

### Source de vérité compétitive

Le gameplay affiché dans `GameScreen` provient du backend FastAPI V14 : Godot rejoue `initial_state` puis `ticks[]`. Les règles d'élévation, Look Ahead, stamina, pushes uphill/downhill et destructions de coffre sont donc calculées par le même moteur Python que celui qui produit `actions.txt`.

### Frontend

- `BackendAPIService` transmet `mission.elevation_text` à la validation, la simulation asynchrone et le replay.
- `BackendStateAdapter` convertit `elevation_rows` en matrice entière.
- `GameState.elevations` conserve la hauteur de chaque cellule pendant tout le replay.
- `GameBoard` affiche une surface relevée et exactement `elevation` bandes de croûte sous la case.
- Les entités utilisent le centre de la surface relevée, donc héros, machines, coffres et effets restent visuellement attachés au bon niveau.
- Les rochers restent à `0` car cette valeur est un marqueur de parsing, pas le niveau minimal du terrain.

### Compatibilité historique

Si `elevation.txt` est omis, `has_elevation=false`, toute la matrice vaut `0`, le décalage vertical vaut `0` et le rendu reste celui de la version 2D historique.
