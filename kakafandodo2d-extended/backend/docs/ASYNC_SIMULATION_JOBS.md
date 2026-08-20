# Simulation asynchrone

Les routes synchrones `/api/v1/simulations` et `/api/v1/simulations/upload` restent disponibles pour les cartes petites et pour le débogage direct.

Pour Godot et les cartes complexes, utiliser :

```text
POST /api/v1/simulation-jobs
POST /api/v1/simulation-jobs/upload
GET  /api/v1/simulation-jobs/{job_id}
GET  /api/v1/simulation-jobs/{job_id}/result
```

## Workflow

```text
map.txt
  ↓
POST /simulation-jobs ou /simulation-jobs/upload
  ↓
HTTP 202 + job_id
  ↓
GET /simulation-jobs/{job_id}
  ↓
queued / running / completed / failed
  ↓
completed
  ↓
GET /simulation-jobs/{job_id}/result
  ↓
SimulationResponse complet
```

L'upload asynchrone renvoie un objet de statut compact. Il évite donc de demander à Swagger UI d'afficher immédiatement la totalité de centaines de snapshots et évite le timeout de `HTTPRequest` pendant le calcul.

Le résultat final conserve exactement le même `SimulationResponse` que la route synchrone, donc le `GameScreen` et le replay ne changent pas.
