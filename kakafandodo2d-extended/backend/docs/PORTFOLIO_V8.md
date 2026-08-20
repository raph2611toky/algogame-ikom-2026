# portfolio_v8 — stamina, relais, sécurité UNHACK et meilleur score

`portfolio_v8` étend `portfolio_v7` sans modifier les règles du moteur. Les priorités restent : coffres accessibles, déblocages nécessaires par Excavator/Grappler, puis pierres libres ou transportées par les machines.

## Relais de pousseur

Une route de coffre garde une estimation de stamina restante. Si le pousseur courant devrait attendre longtemps, la stratégie compare le coût d'un plan de reprise par l'autre héros. Le coffre peut donc être transmis de F à M puis de M à F. Un héros propriétaire d'une route qui doit `WAIT` pour récupérer les 5 stamina d'un prochain `PUSH_*` n'est jamais détourné vers une pierre.

## Terrain dynamique

Une route directe mémorise la signature du terrain au moment de sa création. Si un Excavator crée un nouveau trou avec `DIG` ou si un Grappler supprime un arbre avec `CUT`, la route est invalidée puis recalculée. Cela empêche de conserver un plan dont un futur `PUSH_*` est devenu impossible ou dangereux.

## Relâche sûre des machines

Avant une action de déplacement qui provoquerait `UNHACK`, plusieurs orientations de la machine sont simulées sur un horizon court. Une orientation susceptible de pousser un coffre dans un trou reçoit une pénalité catastrophique. La stratégie tourne la machine avant de la relâcher ; si aucune orientation ne paraît sûre, elle garde le contrôle avec `WAIT` jusqu'à ce que le coffre ou le terrain change.

## Score par tick et END_GAME anticipé

Chaque snapshot contient `current_score`, calculé par :

```text
C*150 + P*25 + ((S+B)//4) + (T//2)
```

Après une trajectoire, `trim_to_best_score_prefix()` compare le score de tous les ticks. Si un tick antérieur est strictement meilleur que le résultat brut, seuls les ticks jusqu'à ce maximum sont conservés et `actions.txt` se termine par `END_GAME`. Le résultat porte alors `BEST_SCORE_END_GAME`.

Cette optimisation est compatible avec le format du GDD : `END_GAME` peut être émis avant la limite de temps.

## Performance

Sur les cartes moyennes, le nombre de profils de déblocage testés est borné plus fortement qu'en v7. Les petites cartes conservent un budget de recherche plus élevé pour ne pas dégrader la qualité de décision.
