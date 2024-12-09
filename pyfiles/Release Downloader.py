import tkinter as tk
from tkinter import ttk, messagebox
import requests
import subprocess
import os

class GitHubDownloaderGUI:
    def __init__(self, master):
        self.master = master
        master.title("GitHub Release Downloader")
        master.geometry("400x300")

        self.repo_label = ttk.Label(master, text="Repository (owner/repo):")
        self.repo_label.pack(pady=5)

        self.repo_entry = ttk.Entry(master, width=40)
        self.repo_entry.pack(pady=5)

        self.fetch_button = ttk.Button(master, text="Fetch Releases", command=self.fetch_releases)
        self.fetch_button.pack(pady=10)

        self.release_label = ttk.Label(master, text="Select Release:")
        self.release_label.pack(pady=5)

        self.release_combobox = ttk.Combobox(master, width=38, state="readonly")
        self.release_combobox.pack(pady=5)

        self.download_button = ttk.Button(master, text="Add to IDM Queue", command=self.download_release)
        self.download_button.pack(pady=10)

        self.status_label = ttk.Label(master, text="")
        self.status_label.pack(pady=5)

    def fetch_releases(self):
        repo = self.repo_entry.get()
        if not repo:
            messagebox.showerror("Error", "Please enter a repository.")
            return

        url = f"https://api.github.com/repos/{repo}/releases"
        response = requests.get(url)
        if response.status_code == 200:
            releases = response.json()
            self.releases = releases
            release_names = [release['tag_name'] for release in releases]
            self.release_combobox['values'] = release_names
            if release_names:
                self.release_combobox.set(release_names[0])
            self.status_label.config(text="Releases fetched successfully.")
        else:
            messagebox.showerror("Error", f"Failed to fetch releases: {response.status_code}")

    def download_release(self):
        selected_release = self.release_combobox.get()
        if not selected_release:
            messagebox.showerror("Error", "Please select a release.")
            return

        release = next((r for r in self.releases if r['tag_name'] == selected_release), None)
        if not release:
            messagebox.showerror("Error", "Release not found.")
            return

        assets = release.get('assets', [])
        if not assets:
            messagebox.showinfo("Info", "No assets found in the selected release.")
            return

        output_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(output_dir, exist_ok=True)

        # Add all assets to IDM queue
        for asset in assets:
            url = asset['browser_download_url']
            if not self.add_to_idm_queue(url, output_dir):
                messagebox.showerror("Error", f"Failed to add {asset['name']} to IDM queue.")

        # Start downloading with IDM after adding all files
        self.start_idm_download()

    def add_to_idm_queue(self, url, output_dir):
        idm_path = r"C:\Program Files (x86)\Internet Download Manager\IDMan.exe"
        if not os.path.exists(idm_path):
            messagebox.showerror("Error", "IDM not found. Please install IDM or update the path.")
            return False

        file_name = os.path.basename(url)
        file_path = os.path.join(output_dir, file_name)

        if os.path.exists(file_path):
            print(f"File {file_name} already exists, skipping.")
            return True

        command = [idm_path, "/a", "/d", url, "/p", output_dir]
        
        try:
            subprocess.run(command, check=True)
            print(f"Successfully added {file_name} to IDM queue.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error adding {file_name} to IDM queue: {e}")
            return False

    def start_idm_download(self):
        idm_path = r"C:\Program Files (x86)\Internet Download Manager\IDMan.exe"
        
        if os.path.exists(idm_path):
            try:
                subprocess.run([idm_path, "/s"], check=True)  # Start all downloads in the queue
                print("Started downloading all files in IDM.")
                self.status_label.config(text="Started downloading all files in IDM.")
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"Failed to start downloads in IDM: {e}")
        else:
            messagebox.showerror("Error", "IDM not found. Please install IDM or update the path.")

def main():
    root = tk.Tk()
    app = GitHubDownloaderGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
