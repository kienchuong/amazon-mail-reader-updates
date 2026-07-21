from pathlib import Path

from amzmail.bootstrap import initialize_storage
from amzmail.ui import AmazonMailReaderApp


BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    storage = initialize_storage(BASE_DIR)
    if storage is None:
        return
    data_dir, vault = storage
    app = AmazonMailReaderApp(data_dir, vault)
    app.mainloop()


if __name__ == "__main__":
    main()
