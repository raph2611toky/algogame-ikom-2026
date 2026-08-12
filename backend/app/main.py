from __future__ import annotations
from fastapi import FastAPI
from app.api.router import api_router
from app.api.swagger import install_custom_docs
from app.core.config import settings
TAGS_METADATA = [{'name': 'health', 'description': 'État du service local FastAPI.'}, {'name': 'contracts', 'description': 'Contrat stable Godot ↔ FastAPI: alphabet map.txt, actions, timing, ressources et formule de score.'}, {'name': 'maps', 'description': 'Validation et interprétation de map.txt sans lancer de simulation.'}, {'name': 'simulations', 'description': 'Calcul IA, replay exact des actions et récupération du fichier actions.txt.'}]

def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version='0.3.2', description="Backend local de simulation et d'IA pour KAKAFANDODO / AlgoGames 2. La logique du jeu reste indépendante des animations Godot.\n\n**Documentation:** `/docs` utilise une vue Swagger complète. Les routes multipart sont affichées en paramètres `formData` explicites, tandis que `/openapi.json` reste le schéma OpenAPI 3.1 canonique de FastAPI.", docs_url=None, redoc_url=None, openapi_tags=TAGS_METADATA, swagger_ui_parameters={'deepLinking': True})
    app.include_router(api_router, prefix=settings.api_prefix)
    install_custom_docs(app)
    return app
app = create_app()
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app.main:app', host=settings.host, port=settings.port, reload=False)
