import uvicorn
from src.config import PORT, DEBUG
from src.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("run:app", host="0.0.0.0", port=PORT, reload=DEBUG)
