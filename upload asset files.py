import os
import subprocess

folder_path = input("Enter folder path: ").strip()
release_tag = input("Enter Release Tag: ").strip()

for name in os.listdir(folder_path):
    file_path = os.path.join(folder_path, name)

    if os.path.isfile(file_path):
        subprocess.run([
            "gh", "release", "upload",
            release_tag, file_path, "--clobber"
        ], check=True)