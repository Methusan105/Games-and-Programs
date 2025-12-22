import tkinter as tk
from tkinter import filedialog, messagebox
import py7zr
import os

def select_input():
    path = filedialog.askopenfilename()  # or askdirectory() if you prefer folders
    if path:
        input_entry.delete(0, tk.END)
        input_entry.insert(0, path)

def select_output_archive():
    path = filedialog.asksaveasfilename(defaultextension=".7z",
                                        filetypes=[("7z archives", "*.7z")])
    if path:
        output_entry.delete(0, tk.END)
        output_entry.insert(0, path)

def select_archive_to_extract():
    path = filedialog.askopenfilename(filetypes=[("7z archives", "*.7z")])
    if path:
        extract_archive_entry.delete(0, tk.END)
        extract_archive_entry.insert(0, path)

def select_extract_dest():
    path = filedialog.askdirectory()
    if path:
        extract_dest_entry.delete(0, tk.END)
        extract_dest_entry.insert(0, path)

def create_archive():
    src = input_entry.get().strip()
    dst = output_entry.get().strip()
    pwd = password_entry.get().strip() or None

    if not src or not dst:
        messagebox.showerror("Error", "Please select input and output paths.")
        return

    try:
        with py7zr.SevenZipFile(dst, "w", password=pwd) as archive:
            if os.path.isdir(src):
                # Write directory contents
                archive.writeall(src, arcname=os.path.basename(src))
            else:
                # Write single file
                archive.write(src, arcname=os.path.basename(src))
        messagebox.showinfo("Success", f"Archive created:\n{dst}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create archive:\n{e}")

def extract_archive():
    arc = extract_archive_entry.get().strip()
    dest = extract_dest_entry.get().strip()
    pwd = extract_password_entry.get().strip() or None

    if not arc or not dest:
        messagebox.showerror("Error", "Please select archive and destination.")
        return

    try:
        with py7zr.SevenZipFile(arc, "r", password=pwd) as archive:
            archive.extractall(path=dest)
        messagebox.showinfo("Success", f"Extracted to:\n{dest}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to extract archive:\n{e}")

root = tk.Tk()
root.title("7z GUI (py7zr)")

# Create frame for compression
frame_comp = tk.LabelFrame(root, text="Create 7z archive")
frame_comp.pack(fill="x", padx=10, pady=5)

tk.Label(frame_comp, text="Input file/dir:").grid(row=0, column=0, sticky="w")
input_entry = tk.Entry(frame_comp, width=50)
input_entry.grid(row=0, column=1, padx=5, pady=2)
tk.Button(frame_comp, text="Browse", command=select_input).grid(row=0, column=2, padx=5)

tk.Label(frame_comp, text="Output archive:").grid(row=1, column=0, sticky="w")
output_entry = tk.Entry(frame_comp, width=50)
output_entry.grid(row=1, column=1, padx=5, pady=2)
tk.Button(frame_comp, text="Browse", command=select_output_archive).grid(row=1, column=2, padx=5)

tk.Label(frame_comp, text="Password (optional):").grid(row=2, column=0, sticky="w")
password_entry = tk.Entry(frame_comp, width=50, show="*")
password_entry.grid(row=2, column=1, padx=5, pady=2)

tk.Button(frame_comp, text="Create archive", command=create_archive).grid(row=3, column=1, pady=5)

# Create frame for extraction
frame_ext = tk.LabelFrame(root, text="Extract 7z archive")
frame_ext.pack(fill="x", padx=10, pady=5)

tk.Label(frame_ext, text="Archive:").grid(row=0, column=0, sticky="w")
extract_archive_entry = tk.Entry(frame_ext, width=50)
extract_archive_entry.grid(row=0, column=1, padx=5, pady=2)
tk.Button(frame_ext, text="Browse", command=select_archive_to_extract).grid(row=0, column=2, padx=5)

tk.Label(frame_ext, text="Destination folder:").grid(row=1, column=0, sticky="w")
extract_dest_entry = tk.Entry(frame_ext, width=50)
extract_dest_entry.grid(row=1, column=1, padx=5, pady=2)
tk.Button(frame_ext, text="Browse", command=select_extract_dest).grid(row=1, column=2, padx=5)

tk.Label(frame_ext, text="Password (optional):").grid(row=2, column=0, sticky="w")
extract_password_entry = tk.Entry(frame_ext, width=50, show="*")
extract_password_entry.grid(row=2, column=1, padx=5, pady=2)

tk.Button(frame_ext, text="Extract archive", command=extract_archive).grid(row=3, column=1, pady=5)

root.mainloop()
