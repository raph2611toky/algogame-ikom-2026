# Version 3D dynamique locale

## 1. Plateau réellement 3D

`GameBoard` reste un `Control` afin de rester compatible avec les scènes UI existantes, mais il embarque maintenant :

- `SubViewportContainer` ;
- `SubViewport` avec monde 3D indépendant ;
- `Camera3D` orthographique ;
- éclairages 3D ;
- blocs de terrain `BoxMesh` regroupés par élévation via `MultiMesh` ;
- surfaces supérieures des cases via un second `MultiMesh` ;
- props et personnages en `Sprite3D`.

Cela permet de conserver les vrais PNG/SVG déjà présents dans le projet tout en donnant de la profondeur réelle aux cases.

## 2. Une hauteur par case

Chaque cellule possède :

```text
(x, y, z)
```

avec `z = height_map[y][x]`.

La section :

```text
ELEVATION
1 2 3 ...
...
```

accepte `0..9` pour compatibilité, et les nouvelles cartes de stress utilisent `1..9`.

## 3. Auto-fit 10 / 100 / 1000 cases

Le nombre de cases n'est pas codé en dur.

La caméra calcule les bornes de la carte dans son espace local puis ajuste automatiquement `Camera3D.size` en prenant en compte :

- largeur ;
- hauteur ;
- ratio du viewport ;
- élévation maximale ;
- marge pour les personnages et objets.

Ainsi, le plateau entre automatiquement dans la zone de jeu même quand les dimensions changent fortement.

## 4. LOD

- `<= 400` cases : détail maximal ;
- `401..1200` : mode compact ;
- `> 1200` : grande carte.

Les labels d'altitude par case sont volontairement masqués quand la carte devient trop dense, mais les volumes 3D et couleurs de niveaux restent présents.

Le `SubViewportContainer.stretch_shrink` réduit aussi le coût GPU des grandes cartes.

## 5. Objets et personnages

Chaque élément utilise le centre de sa cellule comme ancre :

```text
world_x = col
world_z = row
world_y = hauteur_de_la_case
```

Ikotofosa, Imahaki, excavateur, grappler, coffres et props ne dépendent donc pas de la taille écran ou du nombre total de cases.

## 6. Simulation locale

Le parser, `GameState`, `SimulationEngine`, `DemoBrain` et `LocalSimulationRunner` utilisent déjà `width` et `height` provenant de la carte. Les cartes 10/100/1000 cases utilisent exactement le même pipeline.

Aucune requête HTTP n'est nécessaire.

`GameState` maintient aussi un index spatial des rochers, arbres, trous et buissons. Le solveur et le replay parcourent donc les objets présents au lieu de rescanner systématiquement toute la grille à chaque tick.

## 7. Règle d'élévation future

Le rendu lit `height_map`, mais le moteur ne bloque pas encore un déplacement suivant le delta Z. Ce comportement reste volontaire afin de ne pas inventer la règle du twist.

Le point d'extension principal sera :

```gdscript
SimulationEngine._hero_transition(...)
```

et le solveur correspondant dans `DemoBrain`/l'IA de compétition.

## Navigation 3D grande carte — v2

Le plateau n'essaie plus de compresser toutes les cases à l'écran. Les cases gardent une taille de monde constante et la caméra affiche une fenêtre de jeu lisible.

- Glisser gauche ou molette maintenue : déplacer la caméra sur le plateau.
- Molette : zoom avant/arrière.
- Clic droit + glisser : rotation libre de la vue isométrique (yaw + inclinaison bornée).
- WASD / flèches : déplacement clavier relatif à la vue.
- `R` ou `Home` : retour au suivi d'Ikotofosa/Imahaki.
- `F` : cadrage de toute la carte, utile comme vue d'ensemble.
- Sur une carte très grande, le démarrage se fait autour des deux héros plutôt qu'au milieu d'une zone éventuellement vide.
- Les labels d'élévation sont générés seulement autour de la zone visible, afin de rester utilisables sur 1000 cases et plus.
- Les objets et personnages ont été agrandis proportionnellement aux nouvelles cases.
