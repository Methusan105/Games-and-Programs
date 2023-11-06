import os
import time
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import subprocess
import threading

for i in range(1, 71):
    number_str = str(i).zfill(3)
    url = f"https://github.com/Methusan105/Games-and-Programs/releases/download/FH5RA/Forza.Horizon.5.Rally.Adventure.zip.{number_str}"
    command = f'"C:\\Program Files (x86)\\Internet Download Manager\\IDMan.exe" /a /d {url}'
    os.system(command)
os.system(f'"C:\\Program Files (x86)\\Internet Download Manager\\IDMan.exe" /s')

# Function to select the extraction path
def select_extraction_path():
    global extraction_path
    extraction_path = filedialog.askdirectory()
    extraction_path_label.config(text="Extraction Path: " + extraction_path)

# Function to run the extraction in a separate thread
def run_extraction_thread():
    extract_button.config(state="disabled")  # Disable the button during extraction
    try:
        download_directory = os.path.expanduser("~/Downloads")
        zip_file_name = "Forza.Horizon.5.Rally.Adventure.zip"

        # Check if all zip parts exist
        all_parts_exist = all(
            os.path.exists(os.path.join(download_directory, f"{zip_file_name}.{part_number:03d}"))
            for part_number in range(1, 71)
        )

        if not all_parts_exist:
            messagebox.showerror("Error", "Not all zip parts exist.")
            return

        # Trigger the 7zG extraction command
        extract_command = f'7zG x "{os.path.join(download_directory, zip_file_name)}.001" -o"{extraction_path}"'
        subprocess.run(extract_command, shell=True, check=True)

        # If the extraction was successful, delete zip parts
        for part_number in range(1, 71):
            part_path = os.path.join(download_directory, f"{zip_file_name}.{part_number:03d}")
            if os.exists(part_path):
                os.remove(part_path)

        messagebox.showinfo("Extraction Complete", "Extraction and cleanup completed successfully.")
    except Exception as e:
        messagebox.showerror("Extraction Error", f"An error occurred during extraction: {str(e)}")
    finally:
        extract_button.config(state="normal")  # Re-enable the button after extraction

# Function to run the extraction in a separate thread
def run_extraction():
    threading.Thread(target=run_extraction_thread).start()

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

# Button to start the extraction
extract_button = tk.Button(root, text="Extract", command=run_extraction)
extract_button.pack()

# Start the tkinter main loop
root.mainloop()
