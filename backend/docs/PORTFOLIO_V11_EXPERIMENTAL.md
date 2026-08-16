# Portfolio v11 experimental — priorité stricte / anti-détours

Cette variante hérite intégralement de `portfolio_v10` et ne remplace aucun planner de coffre,
aucun planner machine, aucun relais stamina et aucune règle de sécurité.

Modification volontairement limitée : tant qu'il reste au moins un coffre, une collecte de pierre
secondaire n'est autorisée que si la pierre (ou la machine qui la transporte) se trouve dans un
rayon Manhattan <= 3 d'au moins un coffre restant. Les pierres plus lointaines sont reportées à la
phase où les coffres sont terminés ou ne sont plus productifs.

Important : la régression 15x20 montre qu'une politique trop stricte peut modifier indirectement le
positionnement futur des héros et dégrader le nombre de coffres sécurisés. Pour cette raison,
`portfolio_v10` reste la stratégie par défaut tant que v11 n'égale pas ou dépasse v10 sur le corpus
complet. V11 reste disponible pour comparaison depuis `/api/v1/strategies`.
