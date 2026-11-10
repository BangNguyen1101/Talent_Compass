from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://talent:talent@localhost:5432/talentcompass"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 24
    frontend_url: str = "http://localhost:3000"

    # AI
    anthropic_api_key: str | None = None
    # Model rẻ, nhanh: trích xuất CV, soạn JD, sinh câu hỏi
    llm_fast_model: str = "claude-haiku-5-5"
    # Model mạnh: chấm điểm CV, đánh giá câu trả lời phỏng vấn
    llm_smart_model: str = "claude-sonnet-5-5"
    # Khi không có API key -> trả dữ liệu mẫu để chạy thử giao diện
    llm_mock: bool = False

    @property
    def sqlalchemy_url(self) -> str:
        # Render cấp URL dạng postgres:// hoặc postgresql:// -> ép dùng driver psycopg 3
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def use_mock_llm(self) -> bool:
        return self.llm_mock or not self.anthropic_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
