# Use an official lightweight Python runtime
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install system dependencies required for geospatial libraries (rasterio, shapely, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from the backend folder and install them
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend code and data into the container
COPY backend/ ./backend/
COPY data/ ./data/

# Hugging Face Spaces routes traffic to port 7860 by default
EXPOSE 7860

# Run the FastAPI server using Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
