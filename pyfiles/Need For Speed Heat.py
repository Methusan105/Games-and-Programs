import os
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import requests
from tqdm import tqdm
from subprocess import run, PIPE
from concurrent.futures import ThreadPoolExecutor

# Function to select the extraction path
def select_extraction_path():
    global extraction_path
    extraction_path = filedialog.askdirectory()
    extraction_path_label.config(text="Extraction Path: " + extraction_path)

# Function to get file size in bytes
def get_file_size(file_path):
    return os.path.getsize(file_path) if os.path.exists(file_path) else 0

# Function to download assets with progress bar
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
            with open(file_name, 'wb') as file, tqdm(
                desc=os.path.basename(asset_url),
                total=int(response.headers.get('content-length', 0)),
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        bar.update(len(chunk))
    except Exception as e:
        print(f"An error occurred during download: {str(e)}")

def download_assets_with_progress(destination_folder, assets, callback):
    # Create the destination folder if it doesn't exist
    os.makedirs(destination_folder, exist_ok=True)

    # Use ThreadPoolExecutor to limit concurrent downloads to 5
    with ThreadPoolExecutor(max_workers=5) as executor:
        for asset in assets:
            executor.submit(download_asset, asset, destination_folder)

    callback()  # Notify that the download is complete


# Function to run the extraction
def run_extraction(destination_folder):
    try:
        # Trigger the 7zG extraction command
        extract_command = f'7zG x "{os.path.join(destination_folder, "Need.For.Speed.Heat.zip.001")}" -o"{extraction_path}"'
        run(extract_command, shell=True, check=True)

        # If the extraction was successful, delete downloaded assets
        for asset in assets:
            file_name = os.path.join(destination_folder, os.path.basename(asset['browser_download_url']))
            if os.path.exists(file_name):
                os.remove(file_name)

        messagebox.showinfo("Extraction Complete", "Extraction and cleanup completed successfully.")
    except Exception as e:
        messagebox.showerror("Extraction Error", f"An error occurred during extraction: {str(e)}")
    finally:
        download_button.config(state="normal")  # Re-enable the button after extraction

# Function to handle the download completion and initiate extraction
def download_complete_callback():
    run_extraction(destination_folder)

# Create a tkinter window
root = tk.Tk()
root.title("Zip Extraction Tool")

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

# Specify the destination folder
destination_folder = r'C:\Downloads'  # Change this to your desired folder

# Define the GitHub repository details
owner = "Methusan105"
repo = "Games-and-Programs"
tag = "NFSH"

# Get the release information
url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
response = requests.get(url)
release_data = response.json()

# Get the assets
assets = release_data['assets']

# Button to start the download
download_button = tk.Button(root, text="Download", command=lambda: download_assets_with_progress(destination_folder, assets, download_complete_callback))
download_button.pack()

# Start the tkinter main loop
root.mainloop()
