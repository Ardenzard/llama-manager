"""
Entry point when the package is run as a module::

    python -m app
"""

import tkinter as tk
from .app import LlamaManagerApp


def main() -> None:
    root = tk.Tk()
    LlamaManagerApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
