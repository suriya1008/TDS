# /// script
# requires-python = ">=3.12"
# dependences = [
#    "fastapi",
#    "uvicorn",
#    "requests",
# ]
# ///

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # Ensure this import is correct

app = FastAPI()

app.add_middleware(
    CORSMiddleware,  # Use the correct class name here
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)

@app.get("/")
def home():
    return "Yay TDS done. Good Job"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)