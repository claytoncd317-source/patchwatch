import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .database import init_db
from .agent import run_agent
from .models import QueryRequest, QueryResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="PatchWatch",
    description="Vulnerability intelligence agent powered by Claude AI",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("app/static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patchwatch"}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_agent, request.question)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    return QueryResponse(
        question=request.question,
        sql=result["sql"],
        results=result["results"],
        answer=result["answer"],
        row_count=result["row_count"]
    )


@app.get("/schema")
async def schema():
    from .database import get_schema
    return {"schema": get_schema()}