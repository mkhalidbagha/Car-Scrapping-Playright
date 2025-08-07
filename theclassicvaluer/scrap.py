from playwright.sync_api import sync_playwright
import csv
import time
from datetime import datetime

def scrape_vehicle_details(page, url):
    """Scrape individual vehicle details from a vehicle page"""
    try:
        page.goto(url)
        page.wait_for_timeout(3000)  # Reduced timeout for efficiency
        
        # Scrape price range
        price_range = ""
        price_elements = page.locator("h2:has-text('£')").all()
        if price_elements:
            price_range = price_elements[0].text_content().strip()
        
        # Scrape title (year and make/model)
        title = ""
        title_elements = page.locator("h2").all()
        for element in title_elements:
            text = element.text_content().strip()
            if text and not text.startswith('£'):
                title = text
                break
        
        # Parse title to extract year, make, and model
        year = ""
        make = ""
        model = ""
        if title:
            parts = title.split()
            if parts:
                year = parts[0]  # First part should be year
                if len(parts) > 1:
                    make = parts[1]  # Second part should be make
                if len(parts) > 2:
                    model = " ".join(parts[2:])  # Rest is model
        
        # Scrape meta information (auction house, country, date, lot)
        meta_info = ""
        meta_elements = page.locator("p:has-text('•')").all()
        if meta_elements:
            meta_info = meta_elements[0].text_content().strip()
        
        # Parse meta information
        auction_house = ""
        country = ""
        date_of_sale = ""
        lot_number = ""
        
        if meta_info:
            meta_parts = [part.strip() for part in meta_info.split('•')]
            if len(meta_parts) >= 1:
                auction_house = meta_parts[0]
            if len(meta_parts) >= 2:
                country = meta_parts[1]
            if len(meta_parts) >= 3:
                date_of_sale = meta_parts[2]
            if len(meta_parts) >= 4:
                lot_number = meta_parts[3]
        
        # Scrape technical details (Manual, mileage, RHD)
        gearbox = ""
        mileage = ""
        lhd_rhd = ""
        
        # Look for specific technical details
        manual_element = page.locator("p:has-text('Manual')").first
        if manual_element.count() > 0:
            gearbox = "Manual"
        
        # Also check for Automatic
        automatic_element = page.locator("p:has-text('Automatic')").first
        if automatic_element.count() > 0:
            gearbox = "Automatic"
        
        miles_elements = page.locator("p:has-text('miles')").all()
        for element in miles_elements:
            text = element.text_content().strip()
            if "miles" in text:
                mileage = text
                break
        
        rhd_element = page.locator("p:has-text('RHD')").first
        if rhd_element.count() > 0:
            lhd_rhd = "RHD"
        
        lhd_element = page.locator("p:has-text('LHD')").first
        if lhd_element.count() > 0:
            lhd_rhd = "LHD"
        
        # Scrape description (the long text paragraph)
        description = ""
        # Look for paragraphs with substantial text content
        description_elements = page.locator("p").all()
        for element in description_elements:
            text = element.text_content().strip()
            if len(text) > 100 and not "•" in text and not text.startswith("Manual") and not "miles" in text and not text in ["RHD", "LHD"]:
                description = text
                break
        
        # Determine if it's a Spyder (convertible/open-top)
        spyder = ""
        if "tourer" in description.lower() or "convertible" in description.lower() or "roadster" in description.lower() or "spyder" in description.lower():
            spyder = "Yes"
        else:
            spyder = "No"
        
        # Return as dictionary for CSV export
        return {
            "Make": make,
            "Model": model,
            "Production Year": year,
            "Date of Sale": date_of_sale,
            "Sold Price": price_range,
            "Gearbox": gearbox,
            "Description": description,
            "Auction House": auction_house,
            "Country of Sale": country,
            "Spyder": spyder,
            "LHD_RHD": lhd_rhd,
            "URL": url
        }
        
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def get_vehicle_links(page):
    """Get all vehicle links from the market page"""
    try:
        page.goto("https://www.theclassicvaluer.com/the-market")
        page.wait_for_timeout(5000)
        
        # All <a> tags inside section
        a_tags = page.locator('#comp-lp1o159y a')
        count = a_tags.count()
        vehicle_links = []
        
        for i in range(count):
            href = a_tags.nth(i).get_attribute('href')
            if href and "/vehicle-details/" in href:
                # Ensure full URL
                if href.startswith("/"):
                    href = f"https://www.theclassicvaluer.com{href}"
                elif href.startswith("http") and "vehicle-details" in href:
                    pass
                else:
                    continue
                vehicle_links.append(href)
        
        return vehicle_links
    
    except Exception as e:
        print(f"Error getting vehicle links: {e}")
        return []

def save_to_csv(data, filename):
    """Save data to CSV file"""
    if not data:
        print("No data to save")
        return
    
    fieldnames = [
        "Make", "Model", "Production Year", "Date of Sale", "Sold Price", 
        "Gearbox", "Description", "Auction House", "Country of Sale", 
        "Spyder", "LHD_RHD", "URL"
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"✅ Data saved to {filename}")

def main():
    """Main function to orchestrate the scraping process"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"vehicle_data_{timestamp}.csv"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            # Get all vehicle links
            print("🔍 Getting vehicle links from the market page...")
            vehicle_links = get_vehicle_links(page)
            
            if not vehicle_links:
                print("❌ No vehicle links found!")
                return
            
            print(f"🚗 Found {len(vehicle_links)} vehicle links")
            
            # Initialize data storage
            all_vehicle_data = []
            
            # Scrape each vehicle
            for i, link in enumerate(vehicle_links, 1):
                print(f"\n📄 Scraping vehicle {i}/{len(vehicle_links)}: {link}")
                
                vehicle_data = scrape_vehicle_details(page, link)
                
                if vehicle_data:
                    all_vehicle_data.append(vehicle_data)
                    
                    # Print scraped data
                    print(f"✅ {vehicle_data['Make']} {vehicle_data['Model']} ({vehicle_data['Production Year']}) - {vehicle_data['Sold Price']}")
                    
                    # Save after each successful scrape (incremental save)
                    save_to_csv(all_vehicle_data, csv_filename)
                else:
                    print(f"❌ Failed to scrape data from {link}")
                
                # Small delay between requests to be respectful
                time.sleep(2)
            
            # Final summary
            print(f"\n🎉 Scraping completed!")
            print(f"📊 Successfully scraped {len(all_vehicle_data)} vehicles out of {len(vehicle_links)} total")
            print(f"💾 Data saved to: {csv_filename}")
            
        except Exception as e:
            print(f"❌ An error occurred: {e}")
        
        finally:
            input("\nPress Enter to close browser...")
            browser.close()

if __name__ == "__main__":
    main()