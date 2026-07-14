from pydantic import BaseSettings

class Settings(BaseSettings):
    data_dir: str = "data"
    default_players_count: int = 100

    class Config:
        env_prefix = "FBSIM_"

settings = Settings()