# app.py
import sys
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QTextEdit,
    QLineEdit,
    QFormLayout,
    QMessageBox,
)
from PySide6.QtCore import Qt

from database import init_db, insert_listing
from backend import get_all_listings, get_listing, run_full_analysis


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DistressIQ Local (Prototype)")
        self.resize(1000, 600)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)

        # Left: listings list
        left_layout = QVBoxLayout()
        main_layout.addLayout(left_layout, 1)

        self.listings_list = QListWidget()
        left_layout.addWidget(QLabel("Listings"))
        left_layout.addWidget(self.listings_list)

        btn_refresh = QPushButton("Refresh Listings")
        btn_refresh.clicked.connect(self.load_listings)
        left_layout.addWidget(btn_refresh)

        btn_add_sample = QPushButton("Add Sample Listing")
        btn_add_sample.clicked.connect(self.add_sample_listing)
        left_layout.addWidget(btn_add_sample)

        # Right: details + analysis
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout, 2)

        # Basic info
        self.detail_label = QLabel("Select a listing to see details.")
        self.detail_label.setAlignment(Qt.AlignTop)
        right_layout.addWidget(self.detail_label)

        # Simple form to show address / asking price
        form_layout = QFormLayout()
        self.address_field = QLineEdit()
        self.address_field.setReadOnly(True)
        self.asking_field = QLineEdit()
        self.asking_field.setReadOnly(True)
        form_layout.addRow("Address:", self.address_field)
        form_layout.addRow("Asking Price:", self.asking_field)
        right_layout.addLayout(form_layout)

        # Run analysis button
        self.btn_analyze = QPushButton("Run Full Analysis")
        self.btn_analyze.clicked.connect(self.run_analysis_for_selected)
        right_layout.addWidget(self.btn_analyze)

        # Explanation text
        right_layout.addWidget(QLabel("Explanation (Layman):"))
        self.explanation_box = QTextEdit()
        self.explanation_box.setReadOnly(True)
        right_layout.addWidget(self.explanation_box, 1)

        # Connect list selection
        self.listings_list.currentItemChanged.connect(self.on_listing_selected)

        # Initial load
        self.load_listings()

    def load_listings(self):
        self.listings_list.clear()
        listings = get_all_listings()
        for lst in listings:
            item = QListWidgetItem(
                f"{lst['id']} - {lst['address']} (${lst['asking_price'] or 'N/A'})"
            )
            item.setData(Qt.UserRole, lst["id"])
            self.listings_list.addItem(item)

    def add_sample_listing(self):
        lid = insert_listing(
            address="123 Sample St",
            city="Sampleville",
            state="NY",
            zip_code="12345",
            source="manual",
            asking_price=45000,
        )
        QMessageBox.information(self, "Listing Added", f"Sample listing created with ID {lid}.")
        self.load_listings()

    def on_listing_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if not current:
            self.detail_label.setText("Select a listing to see details.")
            self.address_field.setText("")
            self.asking_field.setText("")
            self.explanation_box.clear()
            return

        listing_id = current.data(Qt.UserRole)
        listing = get_listing(listing_id)
        if not listing:
            return

        self.detail_label.setText(f"Listing ID: {listing_id}")
        self.address_field.setText(listing.get("address") or "")
        asking = listing.get("asking_price")
        self.asking_field.setText(f"${asking:,}" if asking is not None else "N/A")
        self.explanation_box.clear()

    def run_analysis_for_selected(self):
        current = self.listings_list.currentItem()
        if not current:
            QMessageBox.warning(self, "No Selection", "Please select a listing first.")
            return

        listing_id = current.data(Qt.UserRole)
        explanation = run_full_analysis(listing_id)
        self.explanation_box.setPlainText(explanation)
        QMessageBox.information(self, "Analysis Complete", "Analysis finished and explanation updated.")


def main():
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
