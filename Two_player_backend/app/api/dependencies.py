from app.services.game_service import GameService, game_service


def get_game_service() -> GameService:
    return game_service
