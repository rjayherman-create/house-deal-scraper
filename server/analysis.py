def run_underwriting(listing):
    asking = listing.get("asking_price", 0)
    arv = asking * 1.8
    rehab = arv * 0.15
    max_offer = arv * 0.70 - rehab

    return {
        "arv_estimate": arv,
        "rehab_estimate": rehab,
        "max_offer": max_offer
    }
