import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

# --- AUTO-INSTALL DEPENDENCIES ---
def install_dependencies():
    required = ["customtkinter", "yt-dlp"]
    for package in required:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Try to install if missing, but we'll import later to avoid crash
install_dependencies()

import customtkinter as ctk
import yt_dlp

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class YTAudioDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Audio Downloader")
        self.geometry("700x500")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # -- Main Content --
        self.main_frame = ctk.CTkFrame(self, corner_radius=20, fg_color="#121212")
        self.main_frame.grid(padx=40, pady=40, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Header
        self.header_label = ctk.CTkLabel(self.main_frame, text="YOUTUBE AUDIO", font=ctk.CTkFont(size=36, weight="bold"), text_color="#FFFFFF")
        self.header_label.grid(row=0, column=0, pady=(40, 0))
        
        self.subheader_label = ctk.CTkLabel(self.main_frame, text="P R E M I U M   D O W N L O A D E R", font=ctk.CTkFont(size=12, weight="bold"), text_color="#1DB954")
        self.subheader_label.grid(row=1, column=0, pady=(0, 40))

        # URL Input
        self.url_label = ctk.CTkLabel(self.main_frame, text="VIDEO URL", font=ctk.CTkFont(size=10, weight="bold"), text_color="#AAAAAA")
        self.url_label.grid(row=2, column=0, sticky="w", padx=50)
        
        self.url_entry = ctk.CTkEntry(self.main_frame, placeholder_text="https://www.youtube.com/watch?v=...", height=45, corner_radius=10, border_color="#333333", fg_color="#1A1A1A")
        self.url_entry.grid(row=3, column=0, sticky="ew", padx=50, pady=(5, 20))

        # Output Path
        self.path_label = ctk.CTkLabel(self.main_frame, text="SAVE TO", font=ctk.CTkFont(size=10, weight="bold"), text_color="#AAAAAA")
        self.path_label.grid(row=4, column=0, sticky="w", padx=50)
        
        self.path_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.path_frame.grid(row=5, column=0, sticky="ew", padx=50)
        self.path_frame.grid_columnconfigure(0, weight=1)

        self.path_entry = ctk.CTkEntry(self.path_frame, placeholder_text="", height=45, corner_radius=10, border_color="#333333", fg_color="#1A1A1A")
        self.path_entry.grid(row=0, column=0, sticky="ew")
        self.path_entry.insert(0, os.path.join(os.path.expanduser("~"), "Music"))
        
        self.browse_button = ctk.CTkButton(self.path_frame, text="BROWSE", command=self.browse_path, width=80, height=45, corner_radius=10, font=ctk.CTkFont(size=12, weight="bold"), fg_color="#333333", hover_color="#444444")
        self.browse_button.grid(row=0, column=1, padx=(10, 0))

        # Download Button
        self.download_btn = ctk.CTkButton(self.main_frame, text="START DOWNLOAD", command=self.start_download, height=60, corner_radius=15, font=ctk.CTkFont(size=16, weight="bold"), fg_color="#1DB954", hover_color="#1ED760", text_color="#000000")
        self.download_btn.grid(row=6, column=0, sticky="ew", padx=50, pady=30)

        # Progress
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, height=8, corner_radius=4, progress_color="#1DB954", fg_color="#333333")
        self.progress_bar.grid(row=7, column=0, sticky="ew", padx=50)
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self.main_frame, text="Ready to download", font=ctk.CTkFont(size=11), text_color="#888888")
        self.status_label.grid(row=8, column=0, pady=(5, 20))

    def browse_path(self):
        path = filedialog.askdirectory()
        if path:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%').replace('%','')
            try:
                percent = float(p) / 100
                self.progress_bar.set(percent)
                self.status_label.configure(text=f"Downloading: {d.get('_percent_str', '0%')}")
            except:
                pass
        elif d['status'] == 'finished':
            self.status_label.configure(text="Conversion in progress...")
            self.progress_bar.set(0.95)

    def download_thread(self, url, output_folder):
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),
            'progress_hooks': [self.progress_hook],
            'quiet': True,
            'no_warnings': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self.progress_bar.set(1)
            self.status_label.configure(text="Download successful!")
            messagebox.showinfo("Success", "Audio downloaded successfully!")
        except Exception as e:
            self.status_label.configure(text="Error occurred.")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        finally:
            self.download_btn.configure(state="normal")
            self.browse_button.configure(state="normal")
            self.url_entry.configure(state="normal")

    def start_download(self):
        url = self.url_entry.get().strip()
        path = self.path_entry.get().strip()
        
        if not url:
            messagebox.showwarning("Warning", "Please enter a valid YouTube URL.")
            return

        self.download_btn.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        self.url_entry.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="Analyzing URL...")

        thread = threading.Thread(target=self.download_thread, args=(url, path))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    app = YTAudioDownloader()
    app.mainloop()
