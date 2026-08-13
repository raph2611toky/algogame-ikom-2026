# portfolio_v5 — stratégie collaborative

`portfolio_v5` conserve la logique chest-first de `portfolio_v4` et ajoute une orchestration simultanée des deux héros.

Priorités :

1. Si au moins deux coffres sont directement sécurisables, F et M reçoivent des coffres distincts et agissent en parallèle.
2. Si un seul coffre est directement sécurisable, le héros le plus efficace le traite et l'autre prépare un autre coffre bloqué si sa capacité est utile, sinon collecte une pierre rentable.
3. Si aucun coffre n'est directement accessible, les obstacles réellement requis sont analysés. F/Excavator traite les trous et M/Grappler traite les arbres. Les deux peuvent travailler en parallèle sur le même coffre ou sur deux coffres distincts.
4. Un héros non requis pour le déblocage collecte des pierres libres ou des pierres transportées par les machines au lieu d'attendre inutilement.
5. Lorsqu'il ne reste que des pierres, les cibles sont affectées conjointement afin d'éviter que les deux héros poursuivent la même pierre et afin de réduire le makespan de collecte.
6. Les coffres prouvés structurellement impossibles ne provoquent pas de hacks inutiles.

Les règles moteur, buffers machines, coût stamina/battery, score et `actions.txt` restent inchangés.
