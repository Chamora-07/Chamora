import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

# Import the retriever component
# Note: Ensure 'packages/metrics-retriever' is in your PYTHONPATH or installed via uv
from metrics_retriever.router import router as retriever_router
from metrics_retriever.router import manager as retriever_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP PHASE ---
    # Start the Metrics Retriever component
    await retriever_manager.start()
    
    # (Future) await rule_engine_manager.start()
    
    yield
    
    # --- SHUTDOWN PHASE ---
    await retriever_manager.stop()
    # (Future) await rule_engine_manager.stop()

app = FastAPI(
    title="Chamora Metrics Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Plug in the component routers
app.include_router(retriever_router)

@app.get("/")
async def root():
    return {"message": "Chamora Platform is running"}

if __name__ == "__main__":
    import uvicorn
    # Use 0.0.0.0 so it's accessible from outside the container
    uvicorn.run(app, host="0.0.0.0", port=8000)