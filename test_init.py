import tkinter as tk
from llama_manager.app import LlamaManagerApp
import os
import sys

# Set dummy DISPLAY for headless environment
if 'DISPLAY' not in os.environ:
    os.environ['DISPLAY'] = ':99'

try:
    root = tk.Tk()
    # Mocking geometry to avoid issues with some X servers
    root.geometry('1x1+0+0')
    app = LlamaManagerApp(root)
    print("App initialized successfully")
    root.destroy()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
