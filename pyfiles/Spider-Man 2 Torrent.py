import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from subprocess import run
import requests

def select_extraction_path():
    global extraction_path
    extraction_path = filedialog.askdirectory()
    extraction_path_label.config(text=f'Extraction Path: {extraction_path}')

def get_file_size(file_path):
    return os.path.getsize(file_path) if os.path.exists(file_path) else 0

def check_assets_exist(destination_folder, assets):
    for asset in assets:
        file_name = os.path.join(destination_folder, os.path.basename(asset['browser_download_url']))
        expected_size = asset['size']
        existing_size = get_file_size(file_name)
        if existing_size != expected_size:
            return False
    return True

def run_extraction(destination_folder):
    try:
            extract_command = f"7zG x \"{os.path.join(destination_folder, os.path.basename('Spider-Man.2.PC.Port.7z.001'))}\" -o\"{extraction_path}\" -y"
            run(extract_command, shell=True, check=True)
            update_command = f"7zG x \"{os.path.join(destination_folder, os.path.basename('Update.zip.001'))}\" -o\"{extraction_path}\" -y"
            run(update_command, shell=True, check=True)
            for asset in assets:
                file_name = os.path.join(destination_folder, os.path.basename(asset['browser_download_url']))
                if os.path.exists(file_name):
                    os.remove(file_name)
            messagebox.showinfo('Extraction Complete', 'Extraction and cleanup completed successfully.')
    except Exception as e:
        messagebox.showerror('Extraction Error', f'An error occurred during extraction: {str(e)}')
    extract_button.config(state='normal')

def periodic_check_and_extract():
    if check_assets_exist(destination_folder, assets):
        output_label.config(text='All assets found. Starting extraction...')
        root.update()
        for i in range(60, 0, -1):
            output_label.config(text=f'Starting extraction in {i} seconds...')
            root.update()
            time.sleep(1)
        run_extraction(destination_folder)
    else:
        for i in range(60, 0, -1):
            output_label.config(text=f'Checking again in {i} seconds...')
            root.update()
            time.sleep(1)
        output_label.config(text='Checking for assets...')
        root.after(1000, periodic_check_and_extract)

root = tk.Tk()
root.title('Zip Extraction Tool')
window_width = 400
window_height = 200
root.geometry(f'{window_width}x{window_height}')

select_path_button = tk.Button(root, text='Select Extraction Path', command=select_extraction_path)
select_path_button.pack()

extraction_path_label = tk.Label(root, text='Extraction Path: ')
extraction_path_label.pack()

destination_folder = 'C:\\Downloads'
owner = 'Methusan105'
repo = 'Games-and-Programs'
tag = 'SM2PC'
url = f'https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}'
response = requests.get(url)
release_data = response.json()
assets = release_data['assets']

output_label = tk.Label(root, text='')
output_label.pack()

extract_button = tk.Button(root, text='Check and Extract', command=lambda: [extract_button.config(state='disabled'), periodic_check_and_extract()])
extract_button.pack()

root.mainloop()