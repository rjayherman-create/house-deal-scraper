import requests

API_URL = "https://house-deal-scrapper-production.up.railway.app"

def analyze_listing(data: dict):
    url = f"{API_URL}/api/listings/analyze"
    response = requests.post(url, json=data, timeout=20)
    response.raise_for_status()
    return response.json()
from PySide6.QtWidgets import QTextEdit

# inside __init__
self.analysis_btn = QPushButton("Analyze Deal")
self.analysis_btn.clicked.connect(self.on_analyze)

self.analysis_box = QTextEdit()
self.analysis_box.setReadOnly(True)

layout.addWidget(self.analysis_btn)
layout.addWidget(self.analysis_box)
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

    underwriting = result["underwriting"]
    explanation = result["explanation"]

    text = (
        f"--- UNDERWRITING ---\n"
        f"Cash Flow: {underwriting['cash_flow']}\n"
        f"Cap Rate: {underwriting['cap_rate']}\n"
        f"ROI: {underwriting['roi']}\n\n"
        f"--- AI EXPLANATION ---\n"
        f"{explanation}"
    )

    self.analysis_box.setText(text)
