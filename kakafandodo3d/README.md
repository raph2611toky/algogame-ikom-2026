# Kakafandodo — Étape 1 : plan 3D stylisé

Cette branche sert uniquement à valider le terrain 3D et la caméra.

Lancer le projet (`F5`) ouvre `Plan3DPreview.tscn`.

## Ce qui est actif

- lecture de `data/plan_demo/map.txt` ;
- lecture séparée de `data/plan_demo/elevation.txt` ;
- altitudes logiques 1 à 9 ;
- terrain continu en terrasses, sans fentes entre cellules ;
- plateaux clairs et pentes en pierre ;
- caméra perspective orbitale libre ;
- zoom, pan, rotation et cadrage complet.

## Contrôles caméra

- clic droit + glisser : rotation orbitale 360° ;
- clic gauche ou milieu + glisser : déplacement ;
- molette : zoom ;
- WASD ou flèches : déplacement ;
- Q / E : rotation ;
- R / Home : vue isométrique confortable ;
- F : cadrer toute la map.

## Volontairement absent

Aucun personnage, machine, prop ou simulation. Ceux-ci reviendront après validation du plan.

## Plan-only slope correction
The current preview branch validates only the 3D board. Vertical terrace walls were replaced by outward sloped trapezoidal faces. No props or characters are spawned in this step.
