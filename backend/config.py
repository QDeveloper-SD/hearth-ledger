from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path("./data")

    model_config = {"env_prefix": "HEARTH_", "env_file": ".env", "extra": "ignore"}

    @property
    def data_path(self) -> Path:
        return self.data_dir.resolve()

    @property
    def hearth_json(self) -> Path:
        return self.data_path / "hearth.json"

    @property
    def hearth_bak(self) -> Path:
        return self.data_path / "hearth.json.bak"

    @property
    def hearth_lock(self) -> Path:
        return self.data_path / "hearth.json.lock"

    @property
    def config_json(self) -> Path:
        return self.data_path / "config.json"


settings = Settings()
