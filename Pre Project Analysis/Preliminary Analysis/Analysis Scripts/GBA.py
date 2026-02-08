import os
from ftplib import FTP
import zipfile

# -------------------------------
# FTP login
# -------------------------------
FTP_HOST = "dataserv.ub.tum.de"
FTP_USER = "m1782307"
FTP_PASS = "m1782307"

# -------------------------------
# ZIPs that contain the tiles
# -------------------------------
zip_archives = [
    "Height/africa/e055_n30_e060_n25.zip",
    "Height/africa/e050_n30_e055_n25.zip",
    "Height/africa/e050_n25_e055_n20.zip",
    "Height/africa/e055_n25_e060_n20.zip"
]

# -------------------------------
# TIFF files we want
# -------------------------------
wanted_tifs = set([
    "55.0_25.2_55.2_25.0_sr_ss.tif",
    "55.2_25.4_55.4_25.2_sr_ss.tif",
    "55.2_25.2_55.4_25.0_sr_ss.tif",
    "55.4_25.4_55.6_25.2_sr_ss.tif",
    "55.4_25.2_55.6_25.0_sr_ss.tif",
    "54.8_25.2_55.0_25.0_sr_ss.tif",
    "54.8_25.0_55.0_24.8_sr_ss.tif",
    "55.2_25.0_55.4_24.8_sr_ss.tif",
    "55.0_25.0_55.2_24.8_sr_ss.tif",
    "55.0_24.8_55.2_24.6_sr_ss.tif",
])

# -------------------------------
# Output folder in Google Drive
# -------------------------------
OUTPUT_FOLDER = "/content/drive/MyDrive/Final Year Project/data/raw/GBA/TIFF Files"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
print("Output folder:", OUTPUT_FOLDER)

# -------------------------------
# Temporary folder on Colab disk
# -------------------------------
TMP_FOLDER = "/content/temp_gba/"
os.makedirs(TMP_FOLDER, exist_ok=True)

# -------------------------------
# Connect to FTP
# -------------------------------
print(f"\nConnecting to FTP server {FTP_HOST} ...")
ftp = FTP(FTP_HOST)
ftp.login(FTP_USER, FTP_PASS)
print("Connected.")

# -------------------------------
# Download each ZIP, extract needed TIFFs, then delete the ZIP
# -------------------------------
for zip_path in zip_archives:
    folder, zip_name = zip_path.rsplit("/", 1)
    local_zip_path = os.path.join(TMP_FOLDER, zip_name)
    
    print(f"\n➡ Downloading {zip_name} from {folder} ...")

    try:
        # Go to correct directory
        ftp.cwd(folder)

        # Download ZIP to Colab disk
        with open(local_zip_path, "wb") as f:
            ftp.retrbinary(f"RETR " + zip_name, f.write)
        print(f"   ✓ Downloaded: {local_zip_path}")

        # Extract only the TIFFs we want
        with zipfile.ZipFile(local_zip_path, 'r') as z:
            for member in z.namelist():
                base = os.path.basename(member)
                if base in wanted_tifs:
                    print(f"   → Extracting {base} ...")
                    z.extract(member, TMP_FOLDER)

                    # Move the TIFF to Drive output
                    src = os.path.join(TMP_FOLDER, member)
                    dst = os.path.join(OUTPUT_FOLDER, base)
                    os.replace(src, dst)
                    print(f"      ✔ Saved to {dst}")

        # Delete the ZIP (to save space)
        os.remove(local_zip_path)
        print(f"   🗑 Deleted ZIP: {zip_name}")

    except Exception as e:
        print(f"❌ Error with {zip_name}: {e}")

# -------------------------------
# Close FTP
ftp.quit()
print("\nAll TIFFs downloaded and saved!")