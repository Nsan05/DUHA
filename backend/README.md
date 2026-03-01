# Dubai Urban Heat API

This is the FastAPI backend serving the Next.js frontend with data for the Dubai Urban Heat project.

## Running the Server

Make sure you are in the `backend/` directory:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.
You can view the interactive auto-generated documentation at `http://localhost:8000/docs`.

## Endpoints

- `GET /api/communities`: Returns the full enriched GeoJSON for Mapbox to draw the map layers.
- `POST /api/pixel`: Samples all rasters at the clicked location and returns features and raw anomalies.
- `POST /api/predict`: Runs a feature override vector through all 3 ML models and returns new anomalies.
- `POST /api/shap`: Extracts SHAP values for a given coordinate to explain why the pixel is hot/cold.

**Note on Constraints**: Requests to `/api/pixel` outside of the valid Urban Dubai boundary where raster data equals `NaN` will correctly return a `400 Bad Request` to strictly enforce domain boundaries.
