from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://talent:talent@localhost:5432/talentcompass"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 24
    frontend_url: str = "http://localhost:3000"

    # AI: "auto" (mặc định: có key nào dùng key đó, ưu tiên Claude), "anthropic" hoặc "gemini"
    llm_provider: str = "auto"
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    # Tên model Gemini thay đổi theo thời gian: kiểm tra tên hiện hành trên Google AI Studio
    gemini_fast_model: str = "gemini-2.5-flash"
    gemini_smart_model: str = "gemini-2.5-pro"
    # Model rẻ, nhanh: trích xuất CV, soạn JD, sinh câu hỏi
    llm_fast_model: str = "claude-haiku-5-5"
    # Model mạnh: chấm điểm CV, đánh giá câu trả lời phỏng vấn
    llm_smart_model: str = "claude-sonnet-5-5"
    # Khi không có API key -> trả dữ liệu mẫu để chạy thử giao diện
    llm_mock: bool = False
    # Kiểm soát chi phí: số lượt gọi AI tối đa mỗi người/ngày
    daily_ai_quota_per_user: int = 80
    # Ẩn danh khảo sát: nhóm nhỏ hơn ngưỡng này sẽ không hiển thị chi tiết
    survey_min_group_size: int = 5

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
    def provider(self) -> str:
        """Nhà cung cấp thực tế: "anthropic" hoặc "gemini"."""
        choice = (self.llm_provider or "auto").strip().lower()
        if choice in ("anthropic", "gemini"):
            return choice
        if not self.anthropic_api_key and self.gemini_api_key:
            return "gemini"
        return "anthropic"

    @property
    def active_api_key(self) -> str | None:
        return self.gemini_api_key if self.provider == "gemini" else self.anthropic_api_key

    @property
    def use_mock_llm(self) -> bool:
        return self.llm_mock or not self.active_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
