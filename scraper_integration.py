# scraper_integration.py
"""
Integration module for the two scrapers.
Replace the simulation functions in the main FastAPI script with these.
"""

import asyncio
import csv
import os
from datetime import datetime
from pathlib import Path
import pandas as pd

from theclassicvaluer.playwright_code import ImprovedClassicValuerScraper
from classic.classic import *  

async def run_classic_valuer_scraper_real(options: dict = None):
    """
    Real implementation of Classic Valuer scraper
    Replace the simulated version in main.py with this function
    """
    try:
        # Initialize scraper with options
        scraper_options = {
            'headless': options.get('headless', True),  # Set to True for production
            'timeout': options.get('timeout', 30000),
            'delay': options.get('delay', 3000),
            'max_pages': options.get('max_pages', 3),
            'viewport': {'width': 1920, 'height': 1080}
        }
        
        # Create and run scraper
        scraper = ImprovedClassicValuerScraper(scraper_options)
        result = await scraper.scrape()
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'records_found': 0
        }

def run_classic_com_scraper_real(options: dict = None):
    """
    Real implementation of Classic.com scraper
    Replace the simulated version in main.py with this function
    """
    try:
        from playwright.sync_api import sync_playwright
        import re
        
        # Configuration
        OUTPUT_CSV = f"classic_com_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        search_page = options.get('page', 1)
        max_listings = options.get('max_listings', 50)
        
        # Currency conversion helper
        def convert_usd_to_gbp(usd_price: float) -> str:
            conversion_rate = options.get('conversion_rate', 0.76)
            gbp_price = usd_price * conversion_rate
            return f"£{int(gbp_price):,}"
        
        # Normalize price for duplicate checking
        def normalize_price(price_str):
            return int(re.sub(r"[^\d]", "", price_str))
        
        # Load existing entries to check for duplicates
        existing_entries = []
        if os.path.exists(OUTPUT_CSV):
            with open(OUTPUT_CSV, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                existing_entries = list(reader)
        
        def is_duplicate(new_row):
            new_price = normalize_price(new_row["Sold Price"])
            for existing in existing_entries:
                existing_price = normalize_price(existing["Sold Price"])
                if (
                    new_row["Make"] == existing["Make"] and
                    new_row["Model"] == existing["Model"] and
                    new_row["Date of Sale"] == existing["Date of Sale"] and
                    abs(existing_price - new_price) / new_price <= 0.05
                ):
                    return True
            return False
        
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=options.get('headless', True))
            context = browser.new_context()
            main_page = context.new_page()
            
            # Navigate to search page
            search_url = f"https://www.classic.com/search?page={search_page}&result_type=listings"
            main_page.goto(search_url, timeout=60000)
            main_page.wait_for_selector("#dealer-listings-table")
            
            # Get listing links
            listings = main_page.query_selector_all("#dealer-listings-table > div.group")
            print(f"Found {len(listings)} listings")
            
            listing_data = []
            for listing in listings[:max_listings]:
                anchor = listing.query_selector("a")
                href = anchor.get_attribute("href") if anchor else None
                
                # Extract gearbox and LHD/RHD info
                og_gearbox = "Unknown"
                LHD_RHD = "Unknown"
                
                try:
                    gearbox_element = listing.query_selector(
                        "div.flex.flex-wrap.justify-between.text-gray-500.table\\:justify-start.table\\:gap-x-3.table\\:gap-y-1 > div:nth-child(2)"
                    )
                    if gearbox_element:
                        og_gearbox = gearbox_element.inner_text().strip()
                except:
                    pass
                
                gearbox_divs = listing.query_selector_all("div.flex.items-center")
                if len(gearbox_divs) >= 3:
                    LHD_RHD = gearbox_divs[2].inner_text().strip()
                elif len(gearbox_divs) >= 2:
                    LHD_RHD = gearbox_divs[1].inner_text().strip()
                
                if href:
                    listing_data.append({
                        "url": "https://www.classic.com" + href,
                        "gearbox": og_gearbox,
                        "lhd_rhd": LHD_RHD
                    })
            
            # Scrape each listing
            new_data = []
            for i, item in enumerate(listing_data):
                try:
                    page = context.new_page()
                    page.goto(item['url'])
                    print(f"Scraping {i+1}/{len(listing_data)}: {item['url']}")
                    
                    # Extract title and parse make/model/year
                    title = page.query_selector("h1").inner_text().strip()
                    match = re.match(r"(\d{4}) (.+?) (.+)", title)
                    if not match:
                        continue
                        
                    year = match.group(1)
                    make = match.group(2)
                    model = match.group(3)
                    
                    # Extract price
                    price_element = page.query_selector("text=$")
                    if not price_element:
                        continue
                        
                    price_text = price_element.inner_text()
                    price_usd = int(re.sub(r"[^\d]", "", price_text))
                    price_gbp = convert_usd_to_gbp(price_usd)
                    
                    # Extract sale date
                    try:
                        raw_date = page.locator("text=Jul").nth(0).inner_text().replace('\n', "").strip()
                        sale_date = datetime.strptime(raw_date, "%b %d, %Y").strftime("%d/%m/%Y")
                    except:
                        sale_date = "Unknown"
                    
                    # Extract auction house
                    auction_house = "Unknown"
                    try:
                        page.goto(item['url'] + "?tab=history")
                        page.wait_for_selector("div.tab-item[data-tab='history']")
                        history_blocks = page.query_selector_all("div.flex.flex-col.border-l-\\[1px\\]")
                        
                        if history_blocks:
                            auction_link = history_blocks[0].query_selector("a")
                            if auction_link:
                                auction_house = auction_link.inner_text().strip()
                    except:
                        pass
                    
                    # Check for Spyder variant
                    spyder = any(k in model.lower() for k in ['spyder', 'spider'])
                    
                    # Create result row
                    row = {
                        "Make": make,
                        "Model": model,
                        "Production Year": year,
                        "Date of Sale": sale_date,
                        "Sold Price": price_gbp,
                        "Gearbox": item["gearbox"],
                        "Description": "",
                        "Auction House": auction_house,
                        "Country of Sale": item["lhd_rhd"],
                        "Spyder": spyder,
                        "LHD_RHD": item["lhd_rhd"]
                    }
                    
                    # Check for duplicates
                    if not is_duplicate(row):
                        new_data.append(row)
                        results.append(row)
                    
                    page.close()
                    
                except Exception as e:
                    print(f"Error scraping {item['url']}: {e}")
                    continue
            
            browser.close()
        
        # Save to CSV
        if new_data:
            df = pd.DataFrame(new_data)
            df.to_csv(OUTPUT_CSV, index=False)
            print(f"Saved {len(new_data)} records to {OUTPUT_CSV}")
        
        return {
            'success': True,
            'records_found': len(results),
            'csv_file': OUTPUT_CSV if new_data else None,
            'results': results
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'records_found': 0,
            'results': []
        }

# Updated background task functions for the main FastAPI app
async def scrape_classic_valuer_background(job_id: str, options: dict, scraping_jobs: dict):
    """Enhanced background task for Classic Valuer scraping"""
    try:
        scraping_jobs[job_id]['status'] = 'running'
        scraping_jobs[job_id]['message'] = 'Initializing Classic Valuer scraper...'
        scraping_jobs[job_id]['progress'] = 10
        
        # Update progress
        scraping_jobs[job_id]['progress'] = 25
        scraping_jobs[job_id]['message'] = 'Launching browser and navigating to market page...'
        
        # Run the actual scraper
        result = await run_classic_valuer_scraper_real(options)
        
        scraping_jobs[job_id]['progress'] = 75
        scraping_jobs[job_id]['message'] = 'Processing and saving results...'
        
        if result['success']:
            scraping_jobs[job_id]['status'] = 'completed'
            scraping_jobs[job_id]['message'] = f'Successfully scraped {result["records_found"]} records from Classic Valuer'
            scraping_jobs[job_id]['total_records'] = result['records_found']
            scraping_jobs[job_id]['results'] = result.get('results', [])[:10]  # First 10 for preview
            scraping_jobs[job_id]['csv_file'] = result.get('csv_file')
            scraping_jobs[job_id]['progress'] = 100
        else:
            scraping_jobs[job_id]['status'] = 'failed'
            scraping_jobs[job_id]['message'] = f'Classic Valuer scraping failed: {result.get("error", "Unknown error")}'
            
    except Exception as e:
        scraping_jobs[job_id]['status'] = 'failed'
        scraping_jobs[job_id]['message'] = f'Error in Classic Valuer scraper: {str(e)}'
    
    scraping_jobs[job_id]['completed_at'] = datetime.now().isoformat()

def scrape_classic_com_background(job_id: str, options: dict, scraping_jobs: dict):
    """Enhanced background task for Classic.com scraping"""
    try:
        scraping_jobs[job_id]['status'] = 'running'
        scraping_jobs[job_id]['message'] = 'Initializing Classic.com scraper...'
        scraping_jobs[job_id]['progress'] = 10
        
        scraping_jobs[job_id]['message'] = 'Launching browser and fetching listings...'
        scraping_jobs[job_id]['progress'] = 30
        
        # Run the actual scraper
        result = run_classic_com_scraper_real(options)
        
        scraping_jobs[job_id]['progress'] = 80
        scraping_jobs[job_id]['message'] = 'Processing results...'
        
        if result['success']:
            scraping_jobs[job_id]['status'] = 'completed'
            scraping_jobs[job_id]['message'] = f'Successfully scraped {result["records_found"]} records from Classic.com'
            scraping_jobs[job_id]['total_records'] = result['records_found']
            scraping_jobs[job_id]['results'] = result['results'][:10] if result['results'] else []
            scraping_jobs[job_id]['csv_file'] = result.get('csv_file')
            scraping_jobs[job_id]['progress'] = 100
        else:
            scraping_jobs[job_id]['status'] = 'failed'
            scraping_jobs[job_id]['message'] = f'Classic.com scraping failed: {result.get("error", "Unknown error")}'
            
    except Exception as e:
        scraping_jobs[job_id]['status'] = 'failed'
        scraping_jobs[job_id]['message'] = f'Error in Classic.com scraper: {str(e)}'
    
    scraping_jobs[job_id]['completed_at'] = datetime.now().isoformat()

# Configuration options for each scraper
CLASSIC_VALUER_DEFAULT_OPTIONS = {
    'headless': True,
    'timeout': 30000,
    'delay': 3000,
    'max_pages': 3,
    'viewport': {'width': 1920, 'height': 1080}
}

CLASSIC_COM_DEFAULT_OPTIONS = {
    'headless': True,
    'page': 1,
    'max_listings': 50,
    'conversion_rate': 0.76,  # USD to GBP
    'timeout': 60000
}