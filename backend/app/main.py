from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from app.api.router import api_router
from app.api.swagger import install_custom_docs
from app.core.config import settings
TAGS_METADATA = [{'name': 'health', 'description': 'État du service local FastAPI.'}, {'name': 'contracts', 'description': 'Contrat stable Godot ↔ FastAPI: alphabet map.txt, actions, timing, ressources et formule de score.'}, {'name': 'maps', 'description': 'Validation et interprétation de map.txt sans lancer de simulation.'}, {'name': 'simulations', 'description': 'Calcul IA, replay exact des actions et récupération du fichier actions.txt.'}, {'name': 'settings', 'description': 'Paramètres persistants utilisés par le frontend Godot et stratégie de simulation par défaut.'}, {'name': 'strategies', 'description': 'Catalogue dynamique des stratégies IA disponibles.'}, {'name': 'simulation-jobs', 'description': 'Calculs asynchrones pour éviter les timeouts HTTP sur les cartes complexes.'}]

def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version='0.13.0', description="Backend local de simulation et d'IA pour KAKAFANDODO / AlgoGames 2. La logique du jeu reste indépendante des animations Godot.\n\n**Documentation:** `/docs` utilise une vue Swagger complète. Les routes multipart sont affichées en paramètres `formData` explicites, tandis que `/openapi.json` reste le schéma OpenAPI 3.1 canonique de FastAPI.", docs_url=None, redoc_url=None, openapi_tags=TAGS_METADATA, swagger_ui_parameters={'deepLinking': True})
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.include_router(api_router, prefix=settings.api_prefix)
    install_custom_docs(app)
    return app
app = create_app()
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app.main:app', host=settings.host, port=settings.port, reload=False)
