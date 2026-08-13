# Livrable 3 — Assets 2D, import map, actions.txt et polish

## Contenu

- Assets de rendu 2D dédiés au gameplay : personnages, machines, coffre, gemmes et terrain.
- `GameBoard` ne dessine plus des formes temporaires pour les éléments principaux : il utilise les textures du dossier `assets/game/`.
- Import `map.txt` avec validation stricte du header `H W TEMPS`, du nombre de lignes, de la largeur et des symboles.
- Aperçu complet de la carte avant lancement.
- Résultat détaillé avec les quatre composantes du score.
- Aperçu du `actions.txt` généré.
- Export de `actions.txt` vers un chemin choisi par l'utilisateur.
- Écran de jeu poli avec background, portraits et rendu dynamique.

## Symboles

- `.` vide
- `F` Ikotofosa
- `M` Imahaki
- `#` rocher
- `t` arbre
- `o` trou
- `X` excavateur
- `G` grappler
- `*` coffre
- `+` pierre précieuse
- `@` cachette / buisson

## Assets

Les assets de gameplay sont dans :

- `assets/game/characters/`
- `assets/game/machines/`
- `assets/game/terrain/`
- `assets/game/props/`
- `assets/game/ui/`

Pour une version éligible au prix artistique, remplacer les visuels de prototype par les créations manuelles de l'artiste de l'équipe en conservant les mêmes chemins ou en mettant à jour les `preload()`.
