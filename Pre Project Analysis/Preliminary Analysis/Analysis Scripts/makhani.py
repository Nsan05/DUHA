import requests
import json

# ==========================================
# 1. CONFIGURATION
# ==========================================
TEST_PARCEL_ID = "3730499" 

# Your working token
YOUR_TOKEN = "RlZnVE54QU5DeFA2YXNoWFJyV3dieFY1V1UxZFZYcUQyZ1ZYOFppRXdxTWJxbEdQRWxiZEs5TVVyQ0I0aWVVV0UrY0QzUCtJVXNFSm11a05zWWNhOGRQbUt6bm42WXJHaXhlMXJLNHJ4c0tYTndteUttRHVyR3lKZkh5SzFBTnI0ZGkydjZVVXBEYkc4NlBtOWl1R2lCMDdwbE05ckVBeQ=="

url = "https://www.makani.ae/UnifiedMakaniPhase3ProxyWebService/MakaniPhase3Proxy.svc/SmartSearchResult"

# ==========================================
# 2. SETUP REQUEST
# ==========================================
headers = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.makani.ae/desktop/',
    'Origin': 'https://www.makani.ae',
    'Host': 'www.makani.ae'
}

payload = {
    "InputJson": {
        "featureclass_id": "5",
        "dgis_id": str(TEST_PARCEL_ID),
        "userid": "",
        "sessionid": ""
    },
    "Remarks": "PC-Windows-10.0-Chrome-142.0",
    "Token": YOUR_TOKEN
}

print(f"🕵️ Sending Request for Parcel {TEST_PARCEL_ID}...")

# ==========================================
# 3. EXECUTE
# ==========================================
try:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        
        # --- LOGIC FIX: Handle both Raw and Wrapped JSON ---
        # Sometimes it comes inside 'd', sometimes it comes raw.
        if 'd' in data:
            # If the server wraps it in a string, unwrap it
            if isinstance(data['d'], str):
                data = json.loads(data['d'])
            else:
                data = data['d']

        # --- EXTRACT LOCATION ---
        if 'PARCEL' in data and len(data['PARCEL']) > 0:
            print("\n✅ SUCCESS! Coordinates Found.")
            print("=" * 50)
            
            parcel_data = data['PARCEL'][0]
            shape = parcel_data.get('SHAPE')
            
            if shape:
                # The shape is "Lon, Lat, Lon, Lat..."
                coords = shape.split(',')
                lon = coords[0].strip()
                lat = coords[1].strip()
                
                print(f"📍 Latitude:  {lat}")
                print(f"📍 Longitude: {lon}")
                print(f"🔹 Full Poly: {shape[:60]}...")
            else:
                print("⚠️ Parcel found, but SHAPE data is empty.")
                
            print("=" * 50)
        else:
            print("❌ Server replied 200, but 'PARCEL' list is empty.")
            print("Response:", data)
            
    else:
        print(f"❌ HTTP Error {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Script Error: {e}")