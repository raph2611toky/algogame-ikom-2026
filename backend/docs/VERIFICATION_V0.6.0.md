# Vérification v0.6.0

- 69 tests automatisés.
- Carte GDD officielle : score 380, 1 coffre, 5 pierres, fin `OBJECTIVES_FINISHED`.
- Carte de collaboration utilisateur 10x14 : score 443, 1 coffre, 4 pierres, F et M actifs dès le premier tick.
- Deux coffres directs : les deux héros poussent en parallèle et sécurisent les deux en 3 ticks.
- Deux pierres seules : F et M collectent en parallèle et terminent en 2 ticks.
- Coffre bloqué par trou + pierre secondaire : F/Excavator débloque pendant que M collecte.
- Coffre bloqué par arbre + pierre secondaire : M/Grappler débloque pendant que F collecte.
- Deux coffres piégés spécialisés : F et M travaillent simultanément et les deux coffres sont sécurisés.
- Multipart `/simulations/upload` : le schéma Swagger 2 expose `file` comme `type: file`, `in: formData`, sans `requestBody`.
- Relecture de `actions.txt` : le replay donne le même score et les mêmes objectifs que la simulation originale.
