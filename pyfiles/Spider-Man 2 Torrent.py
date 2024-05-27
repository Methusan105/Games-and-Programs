import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import requests
from subprocess import run

# Function to select the extraction path
def select_extraction_path():
    global extraction_path
    extraction_path = filedialog.askdirectory()
    extraction_path_label.config(text="Extraction Path: " + extraction_path)

# Function to get file size in bytes
def get_file_size(file_path):
    return os.path.getsize(file_path) if os.path.exists(file_path) else 0

# Function to add a torrent to qBittorrent
def add_torrent_to_qbittorrent(torrent_file):
    try:
        qbittorrent_path = r"C:\Program Files\qBittorrent\qbittorrent.exe"
        run(f'"{qbittorrent_path}" --skip-dialog=true "{torrent_file}"', shell=True, check=True)
        messagebox.showinfo("Download Started", f"{os.path.basename(torrent_file)} download started in qBittorrent.")
    except Exception as e:
        messagebox.showerror("Download Error", f"An error occurred during download: {str(e)}")

# Function to check if all files have the correct size
def check_files_correct_size(destination_folder, assets):
    for asset in assets:
        file_path = os.path.join(destination_folder, os.path.basename(asset['browser_download_url']))
        expected_size = asset['size']
        if get_file_size(file_path) != expected_size:
            return False
    return True

# Function to periodically check file sizes and proceed if complete
def wait_for_torrent_completion(destination_folder, spiderman_assets, callback):
    while True:
        if check_files_correct_size(destination_folder, spiderman_assets):
            callback()
            break
        time.sleep(60)  # Check every 60 seconds

# Function to download other assets
def download_other_assets(destination_folder, assets):
    for asset in assets:
        download_asset(asset, destination_folder)
    other_assets_download_complete_callback()

# Function to download a single asset
def download_asset(asset, destination_folder):
    try:
        asset_url = asset['browser_download_url']
        file_name = os.path.join(destination_folder, os.path.basename(asset_url))
        
        # Check if the file exists and has the correct size
        expected_size = asset['size']
        existing_size = get_file_size(file_name)

        if existing_size == expected_size:
            print(f"Skipping {file_name}, already exists with correct size.")
            return

        with requests.get(asset_url, stream=True) as response:
            with open(file_name, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
    except Exception as e:
        print(f"An error occurred during download: {str(e)}")

# Function to run the extraction
def run_extraction(destination_folder, arch):
    try:
        if arch == "Spiderman":
            extract_command = f'7zG x "{os.path.join(destination_folder, os.path.basename("Spider-Man.2.PC.Port.7z.001"))}" -o"{extraction_path}"'
            run(extract_command, shell=True, check=True)
            for asset in spiderman_assets:
                file_name = os.path.join(destination_folder, os.path.basename(asset['browser_download_url']))
                if os.path.exists(file_name):
                    os.remove(file_name)
            messagebox.showinfo("Extraction Complete", "Extraction and cleanup completed successfully.")
            # After extraction, start downloading other assets
            download_other_assets(destination_folder, other_assets)
        elif arch == "Other":
            Update1 = f'7zG x "{os.path.join(destination_folder, os.path.basename("Update.1.4.4.7z.001"))}" -o"{extraction_path}" -y'
            run(Update1, shell=True, check=True)
            Update2 = f'7zG x "{os.path.join(destination_folder, os.path.basename("Update.1.4.5.rar"))}" -o"{extraction_path}" -y'
            run(Update2, shell=True, check=True)
            messagebox.showinfo("Extraction Complete", "Extraction completed successfully.")
    except Exception as e:
        messagebox.showerror("Extraction Error", f"An error occurred during extraction: {str(e)}")
    finally:
        download_button.config(state="normal")  # Re-enable the button after extraction

# Function to handle the import completion and initiate extraction
def spiderman_import_complete_callback():
    run_extraction(destination_folder, "Spiderman")

# Function to handle the download completion of other assets and initiate extraction
def other_assets_download_complete_callback():
    run_extraction(destination_folder, "Other")

# Create a tkinter window
root = tk.Tk()
root.title("Torrent Import and Extraction Tool")

# Set the window dimensions (width x height)
window_width = 400
window_height = 200
root.geometry(f"{window_width}x{window_height}")

# Button to select the extraction path
select_path_button = tk.Button(root, text="Select Extraction Path", command=select_extraction_path)
select_path_button.pack()

# Label to display the selected extraction path
extraction_path_label = tk.Label(root, text="Extraction Path: ")
extraction_path_label.pack()

# Specify the destination folder containing the torrents
destination_folder = r'C:\Torrents'  # Change this to your desired folder containing .torrent files

# Define the GitHub repository details
owner = "Methusan105"
repo = "Games-and-Programs"
tag = "SM2PC"

# Get the release information
url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
response = requests.get(url)
release_data = response.json()

# Get the assets
assets = release_data['assets']

# Separate Spider-Man.2.PC.Port.7z and other assets
spiderman_assets = [asset for asset in assets if "Spider-Man.2.PC.Port.7z" in asset['browser_download_url']]
other_assets = [asset for asset in assets if "Spider-Man.2.PC.Port.7z" not in asset['browser_download_url']]

# Function to import Spider-Man torrents
def import_spiderman_torrents():
    for asset in spiderman_assets:
        add_torrent_to_qbittorrent(os.path.join(destination_folder, os.path.basename(asset['browser_download_url'])))
    wait_for_torrent_completion(destination_folder, spiderman_assets, spiderman_import_complete_callback)

# Button to start the import
download_button = tk.Button(root, text="Import Torrents", command=import_spiderman_torrents)
download_button.pack()

# Start the tkinter main loop
root.mainloop()
