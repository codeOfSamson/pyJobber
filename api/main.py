from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import applications, runs, stats

app = FastAPI(title="Autojobber Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(applications.router)
app.include_router(runs.router)
app.include_router(stats.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
