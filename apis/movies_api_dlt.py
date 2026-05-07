# 2026.04.27 18.00
from fastapi import APIRouter
import requests
import json
import dlt
from dlt.pipeline.exceptions import PipelineStepFailed
from datetime import datetime
from pydantic import BaseModel
from typing import List

class MoviesRequest(BaseModel):
    imdb_ids: List[str]

API_KEY = "86fa3341"
BASE_URL = "http://www.omdbapi.com/"
DB_CONFIG = {"host": "postgresql", "port": 5432, "database": "n8n", "username": "sql_admin", "password": "sql_pass", "connect_timeout": 15}

router = APIRouter()

@dlt.resource(name="movies", max_table_nesting=0)
def movies_resource(data):
    yield from data

# -----------------------------------------------------------------------------
@router.post("/movies")
def get_omdb_movies(req: MoviesRequest):
    imdb_ids = req.imdb_ids
    data = []
    for imdb_id in imdb_ids:
        response = requests.get(BASE_URL, params={
            "i": imdb_id,
            "apikey": API_KEY
        })
        response.raise_for_status()
        movie = response.json()
        movie["_ingested_at"] = datetime.utcnow().isoformat()
        data.append(movie)

    # -----------------------------------------------------------------------------
    pipeline = dlt.pipeline(
        pipeline_name="omdb_movies", 
        destination=dlt.destinations.postgres(credentials=DB_CONFIG), 
        dataset_name="omdb")
    
    try:
        load_info = pipeline.run(movies_resource(data), write_disposition="append")
    
    except Exception as e:
        print(f"Pipeline failed: {e}")
        raise
    
    return {"rows": len(data), "status": "loaded", "load_info": str(load_info), "sample": data[:3]}
