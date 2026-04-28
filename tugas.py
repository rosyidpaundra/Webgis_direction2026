from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import requests
import json
import os

app = FastAPI(title="MapRuteGIS ORS Backend")

# CORS agar frontend bisa akses API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ORS API KEY
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImQ1NjllYTk0MmU3ODQzOTliNjM2MzY0OWRkZDU3ODc2IiwiaCI6Im11cm11cjY0In0="

# Database connection
conn = psycopg2.connect(
    dbname="isochrone_project",
    user="postgres",
    password="Sukses789",
    host="localhost",
    port="5432"
)

# ==========================================
# API ENDPOINTS
# ==========================================

@app.get("/api/points")
def api_get_points():
    """Mengambil koordinat RS dan Fakultas dari Database"""
    cur = conn.cursor()
    cur.execute("SELECT id, ST_X(geom::geometry), ST_Y(geom::geometry) FROM rs LIMIT 1;")
    rs = cur.fetchone()
    cur.execute("SELECT id, ST_X(geom::geometry), ST_Y(geom::geometry) FROM fge LIMIT 1;")
    fge = cur.fetchone()
    cur.close()
    return {
        "rs": {"id": rs[0], "lon": rs[1], "lat": rs[2]},
        "fge": {"id": fge[0], "lon": fge[1], "lat": fge[2]}
    }

@app.get("/api/geocode")
def api_geocode(q: str = Query(..., description="Query pencarian alamat")):
    """Auto-correct / autocomplete lokasi via Nominatim"""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(q)}&format=json&limit=5&countrycodes=id"
        response = requests.get(url, headers={"Accept-Language": "id", "User-Agent": "MapRuteGIS/1.0"}, timeout=10)
        data = response.json()
        results = []
        for item in data:
            results.append({
                "name": item.get("display_name", ""),
                "lat": float(item.get("lat", 0)),
                "lon": float(item.get("lon", 0)),
                "type": item.get("type", ""),
                "icon": item.get("icon", "")
            })
        return {"query": q, "results": results}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/directions")
def api_get_directions(
    from_lat: float = Query(..., description="Latitude asal"),
    from_lon: float = Query(..., description="Longitude asal"),
    to_lat: float = Query(..., description="Latitude tujuan"),
    to_lon: float = Query(..., description="Longitude tujuan"),
    profile: str = Query("driving-car", description="Profil: driving-car, cycling-regular, foot-walking")
):
    """Mendapatkan data rute dari OpenRouteService"""
    url = f"https://api.openrouteservice.org/v2/directions/{profile}?api_key={ORS_API_KEY}&start={from_lon},{from_lat}&end={to_lon},{to_lat}"
    try:
        response = requests.get(url, timeout=30)
        data = response.json()
        if "features" not in data:
            return {"error": "ORS response invalid", "detail": data}
        
        feature = data["features"][0]
        summary = feature["properties"]["summary"]
        geometry = feature["geometry"]
        
        return {
            "distance": summary["distance"],
            "duration": summary["duration"],
            "geometry": geometry,
            "profile": profile
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/isochrone")
def api_get_isochrone(
    lon: float = Query(..., description="Longitude"),
    lat: float = Query(..., description="Latitude"),
    profile: str = Query("driving-car", description="Profil: driving-car, cycling-regular, foot-walking"),
    range_val: int = Query(300, description="Waktu dalam detik (default 300 = 5 menit)")
):
    """Mendapatkan poligon isochrone dari ORS"""
    url = f"https://api.openrouteservice.org/v2/isochrones/{profile}"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    body = {"locations": [[lon, lat]], "range": [range_val], "range_type": "time"}
    try:
        response = requests.post(url, json=body, headers=headers, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# SERVE MAP PAGE
# ==========================================

MAP_HTML_PATH = os.path.join(os.path.dirname(__file__), "map_modern.html")

@app.get("/map", response_class=HTMLResponse)
def show_map():
    """Serve halaman peta modern"""
    if os.path.exists(MAP_HTML_PATH):
        with open(MAP_HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Error: map_modern.html tidak ditemukan</h1>"

@app.get("/")
def root():
    return {"message": "MapRuteGIS ORS Backend", "endpoints": ["/api/points", "/api/geocode", "/api/directions", "/api/isochrone", "/map"]}

# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("tugas:app", host="127.0.0.1", port=8002, reload=True)
