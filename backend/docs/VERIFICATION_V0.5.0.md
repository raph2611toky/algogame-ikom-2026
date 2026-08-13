# Vérification v0.5.0

- `portfolio_v5` est la stratégie par défaut.
- Priorité 1: coffres directement sécurisables.
- Priorité 2: coffres nécessitant un déblocage ciblé F/Excavator et/ou M/Grappler.
- Priorité 3: pierres libres puis pierres portées par les machines.
- Les coffres impossibles même après retrait hypothétique de tous les trous/arbres ne déclenchent aucun hack.
- Dépendances croisées gérées: arbre pouvant bloquer l'Excavator, trou pouvant bloquer le Grappler.
- Pré-hack utile: une machine requise peut être neutralisée avant que le partenaire termine le déblocage, afin d'éviter une perte de coffre.
- Repositionnement d'une machine contrôlée lorsqu'elle empêche le plan machine du partenaire.

Régressions principales:

- carte officielle: coffre sécurisé, aucune perte, 5 pierres;
- carte utilisateur avec 2 coffres: coffre direct sécurisé, 2 pierres, aucun hack inutile;
- carte utilisateur avec uniquement le coffre inférieur impossible: 2 pierres, 0 hack, batterie 200;
- corridor trou: Ikotofosa hacke un Excavator, HACK_FILL, puis coffre sécurisé;
- corridor arbre: Imahaki hacke un Grappler, CUT, puis coffre sécurisé.

Suite complète: 61 tests.
