from playwright.sync_api import sync_playwright
from datetime import datetime
import re
import csv
import os

OUTPUT_CSV = "classic_listings.csv"

# Helper: Currency conversion (placeholder)
def convert_usd_to_gbp(usd_price: float) -> str:
    conversion_rate = 0.76  # Example fixed rate
    gbp_price = usd_price * conversion_rate
    return f"£{int(gbp_price):,}"

# Helper: Normalize price for duplicate check
def normalize_price(price_str):
    return int(re.sub(r"[^\d]", "", price_str))

# Load existing entries to check for duplicates
existing_entries = []
if os.path.exists(OUTPUT_CSV):
    with open(OUTPUT_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing_entries.append(row)

def is_duplicate(new_row):
    new_price = normalize_price(new_row["Sold Price"])
    for existing in existing_entries:
        existing_price = normalize_price(existing["Sold Price"])
        if (
            new_row["Make"] == existing["Make"] and
            new_row["Model"] == existing["Model"] and
            new_row["Date of Sale"] == existing["Date of Sale"] and
            abs(existing_price - new_price) / new_price <= 0.05  # allow ±5%
        ):
            return True
    return False

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    main_page = context.new_page()

    # STEP 1: Get links and gearbox info
    main_page.goto("https://www.classic.com/search/?filters[make]=4&filters[model]=70&q=Ferrari+430+Coupe+Manual+2004+-+2009&result_type=listings", timeout=60000) # search query will be updated based on the make, model etc 
    main_page.wait_for_selector("#dealer-listings-table")

    listings = main_page.query_selector_all("#dealer-listings-table > div.group")
    print(f"Found {len(listings)} listings\n")

    results = []
    for listing in listings:
        anchor = listing.query_selector("a")
        href = anchor.get_attribute("href") if anchor else None
        gearbox = None
        og_gearbox = "Unknown"
        gearbox_divs = listing.query_selector_all("div.flex.items-center")
        
        try:
            gearbox_element = listing.query_selector(
                "div.flex.flex-wrap.justify-between.text-gray-500.table\\:justify-start.table\\:gap-x-3.table\\:gap-y-1 > div:nth-child(2)"
            )
            if gearbox_element:
                og_gearbox = gearbox_element.inner_text().strip()
        except:
            pass
        
        
        LHD_RHD= "Unknown"
        if len(gearbox_divs) >= 3:
            gearbox = gearbox_divs[1].inner_text().strip()
            LHD_RHD = gearbox_divs[2].inner_text().strip() if len(gearbox_divs) > 2 else "Unknown"
            
        if len(gearbox_divs) >= 2:
            gearbox = "Unknown"
            LHD_RHD = gearbox_divs[1].inner_text().strip()
        if href:
            results.append({
                "url": "https://www.classic.com" + href,
                "country": gearbox or "Unknown",
                "gearbox": og_gearbox
            })

    # STEP 2: Scrape each listing
    new_data = []
    for item in results:
        page = context.new_page()
        page.goto(item['url'])
        print(f"\n🔗 Scraping: {item['url']}")
        try:
            title = page.query_selector("h1").inner_text().strip()
            match = re.match(r"(\d{4}) (.+?) (.+)", title)
            year = match.group(1)
            make = match.group(2)
            model = match.group(3)

            # Price
            price_text = page.query_selector("text=$").inner_text()
            price_usd = int(re.sub(r"[^\d]", "", price_text))
            price_gbp = convert_usd_to_gbp(price_usd)

            # Date of sale
            raw_date = page.locator("text=Jul").nth(0).inner_text().replace('\n', "").strip()
            sale_date = datetime.strptime(raw_date, "%b %d, %Y").strftime("%d/%m/%Y")

            # Description
            description = None

            # Auction House
            auction_house = "Unknown"
            try:
                page.goto(item['url'] + "?tab=history")
                page.wait_for_selector("div.tab-item[data-tab='history']")
                history_blocks = page.query_selector_all("div.flex.flex-col.border-l-\\[1px\\]")

                if len(history_blocks) >= 2:
                    auction_link_0 = history_blocks[0].query_selector("a")
                    if auction_link_0:
                        auction_house = auction_link_0.inner_text().strip()
                elif len(history_blocks) == 1:
                    auction_link = history_blocks[0].query_selector("a")
                    if auction_link:
                        auction_house = auction_link.inner_text().strip()

                seller_tag = page.query_selector("a[href*='/dealer/']")
                if seller_tag:
                    auction_house = seller_tag.inner_text().strip()

            except Exception:
                pass

            # Spyder
            spyder = any(k in model.lower() for k in ['spyder', 'spider'])

            row = {
                "Make": make,
                "Model": model,
                "Production Year": year,
                "Date of Sale": sale_date,
                "Sold Price": price_gbp,
                "Gearbox": item["gearbox"],
                "Description": "",
                "Auction House": auction_house,
                "Country of Sale": item["country"],
                "Spyder": spyder,
                "LHD_RHD": LHD_RHD
            }
            
            
            print(row)

            if not is_duplicate(row):
                new_data.append(row)
            else:
                print("⚠️ Duplicate skipped")

        except Exception as e:
            print(f"❌ Error on {item['url']}: {e}")
            continue

    # Save to CSV
    if new_data:
        write_header = not os.path.exists(OUTPUT_CSV)
        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Make", "Model", "Production Year", "Date of Sale", "Sold Price",
                "Gearbox", "Description", "Auction House", "Country of Sale", "Spyder", "LHD_RHD"
            ])
            if write_header:
                writer.writeheader()
            writer.writerows(new_data)
        print(f"\n✅ Saved {len(new_data)} new records to {OUTPUT_CSV}")
    else:
        print("\n✅ No new records to save (all duplicates)")

    browser.close()
