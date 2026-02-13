import os
from ftplib import FTP
import zipfile
from tqdm import tqdm

# -------------------------------
# FTP login
# -------------------------------
FTP_HOST = "dataserv.ub.tum.de"
FTP_USER = "m1782307"
FTP_PASS = "m1782307"

# -------------------------------
# ZIP files to download
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
# Local output folders
# -------------------------------
OUTPUT_FOLDER = r"D:\GBA"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

TMP_FOLDER = os.path.join(OUTPUT_FOLDER, "tmp_zips")
os.makedirs(TMP_FOLDER, exist_ok=True)

print("Output folder:", OUTPUT_FOLDER)

# -------------------------------
# Connect to FTP
# -------------------------------
print(f"\nConnecting to FTP server {FTP_HOST} ...")
ftp = FTP(FTP_HOST)
ftp.login(FTP_USER, FTP_PASS)
print("Connected to FTP.")

# -------------------------------
# Helper to download a file with progress
# -------------------------------
def download_with_progress(ftp_conn, remote_filename, local_path):
    # get total size
    ftp_conn.voidcmd("TYPE I")
    size = ftp_conn.size(remote_filename)

    with open(local_path, "wb") as f, tqdm(
        total=size, unit="B", unit_scale=True, desc=f"Downloading {remote_filename}"
    ) as pbar:
        def callback(data):
            f.write(data)
            pbar.update(len(data))

        ftp_conn.retrbinary(f"RETR {remote_filename}", callback)

# -------------------------------
# Download, extract, delete
# -------------------------------
for idx, zip_path in enumerate(zip_archives, start=1):
    folder, zip_name = zip_path.rsplit("/", 1)
    local_zip_path = os.path.join(TMP_FOLDER, zip_name)

    print(f"\n[{idx}/{len(zip_archives)}] Processing ZIP: {zip_name}")

    try:
        # Navigate to the FTP directory
        ftp.cwd(folder)

        # Download the ZIP with progress
        download_with_progress(ftp, zip_name, local_zip_path)

        # Extract only wanted TIFFs
        with zipfile.ZipFile(local_zip_path, 'r') as z:
            members = z.namelist()
            print(f" → Files in ZIP: {len(members)} total")
            for member in members:
                base = os.path.basename(member)
                if base in wanted_tifs:
                    print(f"   → Extracting {base} ...")
                    z.extract(member, TMP_FOLDER)
                    src = os.path.join(TMP_FOLDER, member)
                    dst = os.path.join(OUTPUT_FOLDER, base)
                    os.replace(src, dst)
                    print(f"      ✔ Saved TIFF: {dst}")

        # Delete the ZIP file
        os.remove(local_zip_path)
        print(f"   🗑 Deleted ZIP: {zip_name}")

    except Exception as e:
        print(f"❌ Error processing {zip_name}: {e}")

# -------------------------------
# Cleanup
ftp.quit()
print("\nAll requested TIFFs downloaded and extracted!")
