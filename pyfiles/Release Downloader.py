import sys
import os
import subprocess
import signal
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QLineEdit, QPushButton, QComboBox, QMessageBox, QHBoxLayout, QSpinBox, QDoubleSpinBox
import requests

class GitHubReleaseDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.releases = []
        self.download_process = None
        self.download_aria2c()

    def initUI(self):
        self.setWindowTitle('GitHub Release Downloader')
        self.setGeometry(100, 100, 400, 300)

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

        stop_quit_layout = QHBoxLayout()
        self.stop_button = QPushButton('Stop', self)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.on_stop_download)
        stop_quit_layout.addWidget(self.stop_button)

        self.quit_button = QPushButton('Quit', self)
        self.quit_button.clicked.connect(self.on_quit)
        stop_quit_layout.addWidget(self.quit_button)
        layout.addLayout(stop_quit_layout)

        connection_layout = QHBoxLayout()
        self.connections_label = QLabel('Connections:')
        connection_layout.addWidget(self.connections_label)
        self.connections_spinbox = QSpinBox(self)
        self.connections_spinbox.setRange(1, 16)
        self.connections_spinbox.setValue(16)
        connection_layout.addWidget(self.connections_spinbox)
        layout.addLayout(connection_layout)

        speed_layout = QHBoxLayout()
        self.speed_label = QLabel('Download speed (KB/s):')
        speed_layout.addWidget(self.speed_label)
        self.speed_spinbox = QDoubleSpinBox(self)
        self.speed_spinbox.setRange(0, 100000)
        self.speed_spinbox.setValue(0)
        self.speed_spinbox.setSuffix(' KB/s')
        self.speed_spinbox.setDecimals(0)
        speed_layout.addWidget(self.speed_spinbox)
        layout.addLayout(speed_layout)

        simultaneous_download_layout = QHBoxLayout()
        self.simultaneous_download_label = QLabel('Simultaneous downloads:')
        simultaneous_download_layout.addWidget(self.simultaneous_download_label)
        self.simultaneous_download_spinbox = QSpinBox(self)
        self.simultaneous_download_spinbox.setRange(1, 10)
        self.simultaneous_download_spinbox.setValue(4)
        simultaneous_download_layout.addWidget(self.simultaneous_download_spinbox)
        layout.addLayout(simultaneous_download_layout)

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

        aria2c_cmd = [
            os.path.join(os.getcwd(), 'aria2c.exe'),
            '--file-allocation=none',
            '--force-sequential=true',
            '-x', str(self.connections_spinbox.value()),
            '-s', str(self.connections_spinbox.value()),
            '-j', str(self.simultaneous_download_spinbox.value()),
            '-d', output_dir,
            '--auto-file-renaming=false',
            '--continue=true'
        ]

        if self.speed_spinbox.value() > 0:
            download_speed = int(self.speed_spinbox.value())
            aria2c_cmd += ['--max-overall-download-limit', f"{download_speed}K"]

        aria2c_cmd += urls

        try:
            self.download_process = subprocess.Popen(aria2c_cmd)
            self.stop_button.setEnabled(True)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, 'Error', f'Download failed: {str(e)}')

    def on_stop_download(self):
        if self.download_process:
            self.download_process.terminate()
            self.download_process.wait()
            self.download_process = None
            self.stop_button.setEnabled(False)
            QMessageBox.information(self, 'Info', 'Download stopped successfully.')

    def on_quit(self):
        if self.download_process:
            self.download_process.terminate()
            self.download_process.wait()
        QApplication.quit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GitHubReleaseDownloader()
    ex.show()
    sys.exit(app.exec_())
