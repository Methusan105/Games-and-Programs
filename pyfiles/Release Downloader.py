import sys
import os
import subprocess
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QLineEdit, QPushButton, QComboBox, QMessageBox
import requests

class GitHubReleaseDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.releases = []
        self.download_aria2c()

    def initUI(self):
        self.setWindowTitle('GitHub Release Downloader')
        self.setGeometry(100, 100, 400, 200)

        layout = QVBoxLayout()

        self.repo_label = QLabel('Enter the repository (owner/repo):')
        layout.addWidget(self.repo_label)

        self.repo_entry = QLineEdit(self)
        layout.addWidget(self.repo_entry)

        self.submit_button = QPushButton('Submit', self)
        self.submit_button.clicked.connect(self.on_submit)
        layout.addWidget(self.submit_button)

        self.release_label = QLabel('Select a release:')
        layout.addWidget(self.release_label)

        self.release_selection = QComboBox(self)
        self.release_selection.setEnabled(False)
        layout.addWidget(self.release_selection)

        self.download_button = QPushButton('Download', self)
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.on_select_release)
        layout.addWidget(self.download_button)

        self.setLayout(layout)

    def download_aria2c(self):
        url = "https://github.com/Methusan105/Games-and-Programs/releases/download/Programs/aria2c.exe"
        local_path = os.path.join(os.getcwd(), "aria2c.exe")

        if not os.path.isfile(local_path):
            try:
                response = requests.get(url)
                response.raise_for_status()
                with open(local_path, 'wb') as file:
                    file.write(response.content)
                QMessageBox.information(self, 'Info', 'aria2c downloaded successfully.')
            except requests.RequestException as e:
                QMessageBox.critical(self, 'Error', f'Failed to download aria2c: {str(e)}')
        else:
            print("aria2c.exe already exists. Skipping download.")

    def fetch_releases(self, repo):
        url = f"https://api.github.com/repos/{repo}/releases"
        response = requests.get(url)
        if response.status_code == 200:
            self.releases = response.json()
            return self.releases
        else:
            raise Exception(f"Failed to fetch releases: {response.status_code}")

    def on_submit(self):
        repo = self.repo_entry.text()
        try:
            self.releases = self.fetch_releases(repo)
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            return

        if not self.releases:
            QMessageBox.information(self, 'Info', 'No releases found.')
            return

        self.release_selection.clear()
        release_names = [release['name'] if release['name'] else release['tag_name'] for release in self.releases]
        self.release_selection.addItems(release_names)
        self.release_selection.setEnabled(True)
        self.download_button.setEnabled(True)

    def on_select_release(self):
        selected_index = self.release_selection.currentIndex()
        selected_release = self.releases[selected_index]
        assets = selected_release.get('assets', [])
        if not assets:
            QMessageBox.information(self, 'Info', 'No assets found in the selected release.')
            return

        output_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(output_dir, exist_ok=True)

        urls = []
        for asset in assets:
            file_path = os.path.join(output_dir, asset['name'])
            if os.path.exists(file_path) and os.path.getsize(file_path) == asset['size']:
                print(f"File {asset['name']} already exists with correct size. Skipping download.")
            else:
                urls.append(asset['browser_download_url'])

        if not urls:
            QMessageBox.information(self, 'Info', 'All files already exist with correct sizes. Nothing to download.')
            return

        aria2c_cmd = [os.path.join(os.getcwd(), 'aria2c.exe'), '--file-allocation=none', '--force-sequential=true', '-x', '16', '-s', '16', '-j', '4', '-d', output_dir, '--auto-file-renaming=false', '--continue=true'] + urls

        try:
            subprocess.run(aria2c_cmd, check=True)
            QMessageBox.information(self, 'Success', 'Download completed!')
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, 'Error', f'Download failed: {str(e)}')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GitHubReleaseDownloader()
    ex.show()
    sys.exit(app.exec_())
