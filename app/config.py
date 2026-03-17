from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_size: str = Field(default="small", alias="MODEL_SIZE")
    device: str = Field(default="cpu", alias="DEVICE")
    compute_type: str = Field(default="int8", alias="COMPUTE_TYPE")
    model_dir: str = Field(default="/models", alias="MODEL_DIR")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
