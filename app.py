from pathlib import Path
from tkinter import Tk, messagebox

from amzmail.bootstrap import initialize_storage

try:
    from amzmail.ui import AmazonMailReaderApp
except ModuleNotFoundError as exc:
    if exc.name != "customtkinter":
        raise
    AmazonMailReaderApp = None


BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    if AmazonMailReaderApp is None:
        root = Tk()
        root.withdraw()
        messagebox.showerror(
            "Thiếu thư viện giao diện",
            "App cần CustomTkinter. Hãy chạy:\n\npython -m pip install -r requirements.txt\n\nrồi mở lại app.",
            parent=root,
        )
        root.destroy()
        return
    storage = initialize_storage(BASE_DIR)
    if storage is None:
        return
    data_dir, vault = storage
    app = AmazonMailReaderApp(data_dir, vault)
    app.mainloop()


if __name__ == "__main__":
    main()

