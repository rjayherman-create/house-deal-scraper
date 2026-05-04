from PySide6.QtWidgets import QApplication
import sys
from ui import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle("House Deal Scraper")
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
