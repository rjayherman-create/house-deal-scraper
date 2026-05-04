from clienfrom PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTextEdit,
    QTableWidget, QTableWidgetItem, QHBoxLayout,
    QLineEdit, QLabel
)
from PySide6.QtGui import QColor
import requests


API_URL = "https://house-deal-scrapper-production.up.railway.app"


def analyze_listing(data: dict):
    url = f"{API_URL}/api/listings/analyze"
    response = requests.post(url, json=data, timeout=20)
    response.raise_for_status()
    return response.json()


def scrape_listings(city: str, state: str, limit: int = 20):
    url = f"{API_URL}/api/listings/scrape"
    payload = {"city": city, "state": state, "limit": limit}
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # -----------------------------------
        # SCRAPER INPUTS (CITY + STATE)
        # -----------------------------------
        input_row = QHBoxLayout()

        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("City (e.g., Phoenix)")
        input_row.addWidget(QLabel("City:"))
        input_row.addWidget(self.city_input)

        self.state_input = QLineEdit()
        self.state_input.setPlaceholderText("State (e.g., AZ)")
        input_row.addWidget(QLabel("State:"))
        input_row.addWidget(self.state_input)

        self.scrape_btn = QPushButton("Scrape Listings")
        self.scrape_btn.clicked.connect(self.on_scrape)
        input_row.addWidget(self.scrape_btn)

        layout.addLayout(input_row)

        # -----------------------------------
        # TABLE SETUP (WITH SCORE COLUMN)
        # -----------------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Address", "City", "State", "Price", "Score"
        ])
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # -----------------------------------
        # ANALYZE BUTTON + TEXT BOX
        # -----------------------------------
        self.analysis_btn = QPushButton("Analyze Deal")
        self.analysis_btn.clicked.connect(self.on_analyze)
        layout.addWidget(self.analysis_btn)

        self.analysis_box = QTextEdit()
        self.analysis_box.setReadOnly(True)
        layout.addWidget(self.analysis_box)

    # -----------------------------------
    # COLOR CODING FOR SCORE
    # -----------------------------------
    def color_for_score(self, score: int) -> QColor:
        if score >= 80:
            return QColor(0, 180, 0)
        elif score >= 60:
            return QColor(200, 160, 0)
        else:
            return QColor(200, 0, 0)

    def make_numeric_item(self, value):
        item = QTableWidgetItem(str(value))
        item.setData(0, value)
        return item

    # -----------------------------------
    # SCRAPE HANDLER
    # -----------------------------------
    def on_scrape(self):
        city = self.city_input.text().strip()
        state = self.state_input.text().strip()

        if not city or not state:
            return

        result = scrape_listings(city, state)
        listings = result["listings"]

        self.table.setRowCount(len(listings))

        for row, listing in enumerate(listings):
            self.table.setItem(row, 0, QTableWidgetItem(str(listing.get("id", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(listing["address"]))
            self.table.setItem(row, 2, QTableWidgetItem(listing["city"]))
            self.table.setItem(row, 3, QTableWidgetItem(listing["state"]))
            self.table.setItem(row, 4, self.make_numeric_item(listing["asking_price"]))
            self.table.setItem(row, 5, QTableWidgetItem(""))  # score empty until analyzed

    # -----------------------------------
    # ANALYZE HANDLER
    # -----------------------------------
    def on_analyze(self):
        row = self.table.currentRow()
        if row < 0:
            return

        listing = {
            "address": self.table.item(row, 1).text(),
            "city": self.table.item(row, 2).text(),
            "state": self.table.item(row, 3).text(),
            "zip_code": "",
            "asking_price": float(self.table.item(row, 4).text()),
        }

        result = analyze_listing(listing)

        score = result["score"]
        underwriting = result["underwriting"]
        explanation = result["explanation"]

        score_item = self.make_numeric_item(score)
        score_item.setForeground(self.color_for_score(score))
        self.table.setItem(row, 5, score_item)

        text = (
            f"--- DEAL SCORE ---\n"
            f"{score}/100\n\n"
            f"--- UNDERWRITING ---\n"
            f"Cash Flow: {underwriting['cash_flow']}\n"
            f"Cap Rate: {underwriting['cap_rate']}\n"
            f"ROI: {underwriting['roi']}\n\n"
            f"--- AI EXPLANATION ---\n"
            f"{explanation}"
        )

        self.analysis_box.setText(text)
t import analyze_listing
