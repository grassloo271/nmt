from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from optimizer import optimize_aircraft


app = FastAPI()


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "https://nmt-sdt0.onrender.com/",
        "https://nmt-1-4vru.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# INPUT FORMAT
# ============================================================

class AircraftInput(BaseModel):
    S: float
    AR: float
    margin: float


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "message": "Aircraft optimizer is running!"
    }


# ============================================================
# OPTIMIZATION ENDPOINT
# ============================================================

@app.post("/aircraft")
def aircraft(
    inputs: AircraftInput
):

    try:

        results = optimize_aircraft(
            S=inputs.S,
            AR=inputs.AR,
            margin=inputs.margin,
        )

        return results

    except Exception as error:

        print(
            "Optimization failed:",
            repr(error)
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )