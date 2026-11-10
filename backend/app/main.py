import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, cvs, interviews, jobs

logging.basicConfig(level=logging.INFO)

settings = get_settings()
app = FastAPI(title="TalentCompass API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_url.split(",") if o.strip()],
    # Cho phép link xem trước (preview) của Vercel
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, jobs.router, cvs.router, interviews.router):
    app.include_router(r)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "llm": "mock" if settings.use_mock_llm else "claude"}
