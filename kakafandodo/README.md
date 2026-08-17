# KAKAFANDODO - Façade frontale 3D (étape 1)

Ce projet Godot 4 contient **uniquement la façade frontale statique de la maison / arche** inspirée de ton image.

## Contenu
- vraie scène 3D Godot
- `Camera3D` placée **frontalement**
- `DirectionalLight3D`
- `WorldEnvironment`
- façade construite en 3D par code (`MeshInstance3D`, `BoxMesh`, `CylinderMesh`, `PrismMesh`, `SphereMesh`)
- textures pierre extraites comme textures de matériau
- **pas de décor complet, pas de personnages, pas de bouton, pas d'image plane comme scène**

## Structure
- `scenes/Main.tscn`
- `scripts/Main.gd`
- `assets/textures/*`
- `assets/reference/facade_reference.png`

## Ouvrir le projet
1. Dézipper le dossier.
2. Dans Godot : **Importer**.
3. Sélectionner `project.godot`.
4. Lancer avec **F5**.

## Étape suivante logique
Quand cette façade te convient, on fera ensuite :
1. les détails encore plus fins du mur et de l'arche
2. l'escalier / muret du bas
3. ensuite seulement le panneau COMMENCER
4. puis les personnages
