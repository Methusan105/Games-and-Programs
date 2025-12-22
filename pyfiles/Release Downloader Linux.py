import sys
import os
import shutil
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QLineEdit, QPushButton,
    QComboBox, QMessageBox, QHBoxLayout, QSpinBox, QDoubleSpinBox
)
from PyQt5.QtCore import QProcess, Qt
import requests

class GitHubReleaseDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.releases = []
        self.repo = None
        self.github_token = None
        self.download_process = None
        self.download_dir = os.path.join(os.getcwd(), "downloads")
        self.initUI()
        self.check_aria2c()

    def initUI(self):
        self.setWindowTitle('GitHub Release Downloader')
        self.setGeometry(100, 100, 420, 450)

        layout = QVBoxLayout()

        # Token input
        self.token_label = QLabel('GitHub Personal Access Token:')
        layout.addWidget(self.token_label)
        self.token_entry = QLineEdit(self)
        self.token_entry.setEchoMode(QLineEdit.Password)
        self.token_entry.setPlaceholderText('ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
        layout.addWidget(self.token_entry)

        # Download folder display
        self.downloads_label = QLabel(f'📁 Download folder: {self.download_dir}')
        self.downloads_label.setStyleSheet("font-weight: bold; color: green;")
        layout.addWidget(self.downloads_label)

        # Repo input
        self.repo_label = QLabel('Enter the repository (owner/repo):')
        layout.addWidget(self.repo_label)
        self.repo_entry = QLineEdit(self)
        layout.addWidget(self.repo_entry)

        self.submit_button = QPushButton('Submit', self)
        self.submit_button.clicked.connect(self.on_submit)
        layout.addWidget(self.submit_button)

        # Release selection
        self.release_label = QLabel('Select a release:')
        layout.addWidget(self.release_label)
        self.release_selection = QComboBox(self)
        self.release_selection.setEnabled(False)
        layout.addWidget(self.release_selection)

        # Download + Delete controls (Delete button ADDED BACK, manual only)
        download_layout = QHBoxLayout()
        self.download_button = QPushButton('Download', self)
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.on_select_release)
        download_layout.addWidget(self.download_button)

        self.delete_button = QPushButton('Delete Matching Assets', self)
        self.delete_button.setStyleSheet("QPushButton { background-color: #ff4444; color: white; font-weight: bold; }")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.on_delete_click)
        download_layout.addWidget(self.delete_button)
        layout.addLayout(download_layout)

        # Progress label
        self.progress_label = QLabel('Ready')
        self.progress_label.setStyleSheet("font-weight: bold; color: blue;")
        self.progress_label.setWordWrap(True)
        layout.addWidget(self.progress_label)

        # Stop / Quit
        stop_quit_layout = QHBoxLayout()
        self.stop_button = QPushButton('Stop', self)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.on_stop_download)
        stop_quit_layout.addWidget(self.stop_button)

        self.quit_button = QPushButton('Quit', self)
        self.quit_button.clicked.connect(self.on_quit)
        stop_quit_layout.addWidget(self.quit_button)
        layout.addLayout(stop_quit_layout)

        # aria2c settings
        connection_layout = QHBoxLayout()
        self.connections_label = QLabel('Connections:')
        connection_layout.addWidget(self.connections_label)
        self.connections_spinbox = QSpinBox(self)
        self.connections_spinbox.setRange(1, 16)
        self.connections_spinbox.setValue(16)
        connection_layout.addWidget(self.connections_spinbox)
        layout.addLayout(connection_layout)

        speed_layout = QHBoxLayout()
        self.speed_label = QLabel('Download speed limit (KB/s):')
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

    def check_aria2c(self):
        aria2c_path = shutil.which('aria2c')
        if aria2c_path is None:
            QMessageBox.warning(
                self, 'Warning',
                'aria2c not found. Install with: sudo apt install aria2'
            )
        else:
            print(f"Found aria2c at {aria2c_path}")

    def fetch_releases(self, repo):
        self.repo = repo
        if not self.github_token:
            raise Exception("GitHub token required")
        
        headers = {"Authorization": f"Bearer {self.github_token}", "Accept": "application/vnd.github+json"}
        url = f"https://api.github.com/repos/{repo}/releases"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            self.releases = response.json()
            return self.releases
        raise Exception(f"Failed to fetch releases: {response.status_code}")

    def on_submit(self):
        self.github_token = self.token_entry.text().strip()
        if not self.github_token:
            QMessageBox.warning(self, 'Warning', 'Enter GitHub token.')
            return

        repo = self.repo_entry.text().strip()
        if not repo:
            QMessageBox.warning(self, 'Warning', 'Enter repository path.')
            return

        try:
            self.releases = self.fetch_releases(repo)
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            return

        if not self.releases:
            QMessageBox.information(self, 'Info', 'No releases found.')
            return

        self.release_selection.clear()
        release_names = [release['name'] or release['tag_name'] for release in self.releases]
        self.release_selection.addItems(release_names)
        self.release_selection.setEnabled(True)
        self.download_button.setEnabled(True)
        self.delete_button.setEnabled(True)

    def on_select_release(self):
        selected_index = self.release_selection.currentIndex()
        selected_release = self.releases[selected_index]
        assets = selected_release.get('assets', [])
        
        os.makedirs(self.download_dir, exist_ok=True)

        urls = []
        for asset in assets:
            file_path = os.path.join(self.download_dir, asset['name'])
            if os.path.exists(file_path) and os.path.getsize(file_path) == asset['size']:
                print(f"Skipping {asset['name']} (exists and matches size)")
            else:
                urls.append(asset['browser_download_url'])

        if not urls:
            self.progress_label.setText('All files exist with correct sizes.')
            return

        self.progress_label.setText(f'Downloading {len(urls)} files...')

        # Enhanced aria2c command for real-time progress + speed display
        aria2c_cmd = [
            'aria2c',
            '--file-allocation=none',
            '--force-sequential=true',
            '-x', str(self.connections_spinbox.value()),
            '-s', str(self.connections_spinbox.value()),
            '-j', str(self.simultaneous_download_spinbox.value()),
            '-d', self.download_dir,
            '--auto-file-renaming=false',
            '--continue=true',
            '--summary-interval=1',        # Update every 1 second
            '--console-log-level=notice',  # Show progress with speeds
            '--human-readable=true',       # Human readable sizes (MiB, GiB)
            '--no-conf'                    # Ignore config files
        ]
        if self.speed_spinbox.value() > 0:
            aria2c_cmd += ['--max-overall-download-limit', f"{int(self.speed_spinbox.value())}K"]
        aria2c_cmd += urls

        # Use QProcess (NON-BLOCKING)
        self.download_process = QProcess(self)
        self.download_process.setProgram(aria2c_cmd[0])
        self.download_process.setArguments(aria2c_cmd[1:])
        
        # Connect signals for real-time output
        self.download_process.readyReadStandardOutput.connect(self.on_download_output)
        self.download_process.readyReadStandardError.connect(self.on_download_error)
        self.download_process.finished.connect(self.on_download_finished)
        self.download_process.stateChanged.connect(self.on_process_state_changed)

        self.stop_button.setEnabled(True)
        self.download_button.setEnabled(False)
        self.download_process.start()

    def on_download_output(self):
        if self.download_process:
            output = self.download_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            print(output, end='')
            lines = output.strip().splitlines()
            if lines:
                # Show last meaningful progress line (contains % and speed)
                for line in reversed(lines):
                    if any(x in line for x in ['%', 'DL:', 'ETA:']):
                        self.progress_label.setText(line[:150])
                        break

    def on_download_error(self):
        if self.download_process:
            error = self.download_process.readAllStandardError().data().decode('utf-8', errors='ignore')
            print(f"aria2c error: {error}", end='')

    def on_download_finished(self, exit_code, exit_status):
        print("Download process finished.")
        self.progress_label.setText('✅ Download completed!')
        self.stop_button.setEnabled(False)
        self.download_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.download_process = None

    def on_process_state_changed(self, new_state):
        states = {QProcess.NotRunning: "Not running", QProcess.Starting: "Starting", 
                 QProcess.Running: "Running"}
        print(f"Process state: {states.get(new_state, 'Unknown')}")

    def on_delete_click(self):
        if not self.releases or self.release_selection.currentIndex() < 0:
            QMessageBox.warning(self, 'Warning', 'Select a release first.')
            return
        selected_release = self.releases[self.release_selection.currentIndex()]
        self.delete_assets_with_local_file(selected_release)

    def delete_assets_with_local_file(self, release):
        """
        Deletes GitHub release assets that have corresponding local files
        with exactly matching sizes. KEEPS local files intact.
        """
        if not self.github_token or not self.repo:
            QMessageBox.warning(self, 'Warning', 'Token or repository information is missing.')
            return

        if not os.path.isdir(self.download_dir):
            QMessageBox.warning(self, 'Warning', f'Downloads folder not found: {self.download_dir}')
            return

        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json"
        }

        # Build local file size cache for efficiency
        local_files = {
            f: os.path.getsize(os.path.join(self.download_dir, f))
            for f in os.listdir(self.download_dir)
            if os.path.isfile(os.path.join(self.download_dir, f))
        }

        print(f"🔍 Checking {len(local_files)} local files in {self.download_dir}")
        deleted = []
        skipped = []
        failed = []

        for asset in release.get('assets', []):
            name = asset.get('name')
            size = asset.get('size')
            asset_id = asset.get('id')

            if not all([name, size is not None, asset_id]):
                print(f"⚠️ Skipping invalid asset: {name}")
                continue

            # Check local match
            if name not in local_files:
                print(f"❌ Skipping {name}: local file not found")
                skipped.append(name)
                continue

            local_size = local_files[name]
            if local_size != size:
                print(f"⚠️ Size mismatch {name}: local={local_size:,} bytes, remote={size:,} bytes")
                skipped.append(name)
                continue

            print(f"🎯 Target for deletion: {name} ({size:,} bytes)")

            # Delete from GitHub ONLY (local file stays)
            delete_url = f"https://api.github.com/repos/{self.repo}/releases/assets/{asset_id}"
            try:
                resp = requests.delete(delete_url, headers=headers)
                if resp.status_code == 204:
                    print(f"✅ Successfully deleted from GitHub: {name}")
                    deleted.append(name)
                else:
                    print(f"❌ Failed to delete {name}: HTTP {resp.status_code}")
                    failed.append(name)
            except Exception as e:
                print(f"❌ Error deleting {name}: {e}")
                failed.append(name)

        # Comprehensive GUI feedback
        msg_parts = []
        if deleted:
            msg_parts.append(f"✅ Deleted {len(deleted)} assets from GitHub (local files kept):")
            msg_parts.extend([f"   • {name}" for name in deleted[:10]])
            if len(deleted) > 10:
                msg_parts.append(f"   ... and {len(deleted)-10} more")
        
        if skipped:
            msg_parts.append(f"⚠️ Skipped {len(skipped)} assets (missing files or size mismatch)")
        
        if failed:
            msg_parts.append(f"❌ {len(failed)} deletion failures - check console")

        if not msg_parts:
            msg_parts = ["ℹ️ No assets were eligible for deletion (no matching files found)"]

        self.progress_label.setText(f'GitHub: {len(deleted)} deleted, local files kept')
        QMessageBox.information(self, "Deletion Report", "\n".join(msg_parts))

    def on_stop_download(self):
        if self.download_process and self.download_process.state() == QProcess.Running:
            self.download_process.terminate()
            self.download_process.waitForFinished(3000)
            if self.download_process.state() == QProcess.Running:
                self.download_process.kill()
            self.download_process = None
            self.stop_button.setEnabled(False)
            self.download_button.setEnabled(True)
            self.delete_button.setEnabled(True)
            self.progress_label.setText('⏹️ Download stopped by user')

    def on_quit(self):
        if self.download_process and self.download_process.state() == QProcess.Running:
            self.download_process.terminate()
            self.download_process.waitForFinished(3000)
        QApplication.quit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GitHubReleaseDownloader()
    ex.show()
    sys.exit(app.exec_())

