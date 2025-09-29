import tkinter as tk
from tkinter import messagebox
from gui.window import MainWindow
from upv.upv_auto_config import main as upv_main

def run_upv_application():
    try:
        upv_main()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to run UPV application: {e}")

def main():
    root = tk.Tk()
    root.title("Mic Sensitivity GUI")
    root.geometry("1280x800")

    main_window = MainWindow(root, run_upv_application)
    main_window.pack(fill=tk.BOTH, expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()
