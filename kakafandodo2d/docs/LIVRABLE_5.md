# Livrable 5 — finition finale UI/UX

Ce livrable finalise la présentation de la version compétition de **Kakafandodo**.

## Inclus

- **Main menu** conformisé à la maquette :
  - grand logo centré
  - bouton `JOUER` dominant
  - boutons secondaires `MISSIONS`, `PARAMÈTRES`, `CRÉDITS`, `QUITTER`
  - personnages repositionnés
  - décorations de premier plan cohérentes
  - petites animations d'entrée et de hover

- **Écran paramètres** rapproché de la maquette :
  - grand logo supérieur
  - plaque `PARAMÈTRES`
  - grand panneau central aspect pierre/bois
  - rangées de réglages homogènes
  - sliders audio
  - sélecteurs gauche/droite pour qualité, plein écran et langue
  - boutons `RETOUR`, `PAR DÉFAUT`, `QUITTER`
  - persistance réelle dans `user://settings.cfg`

- **Packaging compétition** :
  - parcours complet jouable de l'écran d'accueil au résultat
  - README mis à jour
  - structure prête à être remplacée progressivement par les assets artistiques finaux de l'équipe

## Écrans principaux

```text
StartScreen
  -> MainMenu
      -> MissionSelect
          -> MissionLaunch
              -> GameScreen
                  -> ResultScreen
      -> SettingsScreen
      -> CreditsScreen
```

## À remplacer si vous visez une soumission artistique finale

Les assets d'ambiance (backgrounds, logo visuel, personnages de menu) peuvent rester comme **gabarits d'intégration**. Pour une soumission finale propre au concours, remplacez-les par vos versions créées par votre équipe tout en gardant si possible les mêmes chemins de fichiers.

## Recommandation finale avant rendu

1. ouvrir le projet dans Godot 4 ;
2. vérifier les imports ;
3. tester le flux complet ;
4. remplacer si besoin les assets artistiques par vos créations finales ;
5. exporter une build desktop compétition.
