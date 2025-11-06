import tkinter as tk
from tkinter import messagebox
from gui.window import MainWindow
from upv.upv_auto_config import main as upv_main
import sys, traceback, datetime, os

LOG_FILE = "crash_log.txt"

def _log_exception(exc_type, exc_value, exc_tb):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write("\n==== {} ====".format(datetime.datetime.now().isoformat()))
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    try:
        messagebox.showerror("Unhandled Error", f"{exc_type.__name__}: {exc_value}\nSee {LOG_FILE}")
    except Exception:
        pass

sys.excepthook = _log_exception

def run_upv_application():
    try:
        upv_main()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to run UPV application: {e}")

def main():
    root = tk.Tk()
    # Intercept Tk callback exceptions (similar to sys.excepthook)
    def report_callback_exception(exc_type, exc_value, exc_tb):
        _log_exception(exc_type, exc_value, exc_tb)
    root.report_callback_exception = report_callback_exception
    root.title("Mic Sensitivity GUI")
    root.geometry("1280x800")

    main_window = MainWindow(root, run_upv_application)
    main_window.pack(fill=tk.BOTH, expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()
