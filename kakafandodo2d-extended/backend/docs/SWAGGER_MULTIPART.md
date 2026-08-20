# Swagger multipart

`/docs` consomme `/swagger.json` en Swagger 2.0 pour que les fichiers multipart soient décrits comme paramètres `formData` et non comme `requestBody`.

Pour `POST /api/v1/simulations/upload`, la déclaration attendue est :

```json
{
  "name": "file",
  "in": "formData",
  "required": true,
  "type": "file"
}
```

La conversion reconnaît aussi explicitement les noms `file`, `map_file` et `actions_file`. Cela évite qu'une variation de schéma FastAPI/Pydantic transforme accidentellement un `UploadFile` en simple `string` dans la documentation Swagger.

Après mise à jour du backend, redémarrer Uvicorn et recharger `/docs`. Le endpoint réel reste un `UploadFile` FastAPI et les tests multipart envoient de vrais octets de fichier.
