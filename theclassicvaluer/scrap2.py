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

def get_vehicle_links(page, load_more_clicks=5):
    """Get all vehicle links from the market page with Load More functionality"""
    try:
        make = "Ferrari Coupe"
        model = "2004-2009"
        model = "F430"
        
        page.goto("https://www.theclassicvaluer.com/the-market")
        page.wait_for_timeout(5000)
        
        vehicle_links = set()  # Use set to avoid duplicates
        
        # Click "Load More" button multiple times
        for click_count in range(load_more_clicks + 1):  # +1 to include initial load
            if click_count > 0:
                print(f"🔄 Clicking 'Load More' button ({click_count}/{load_more_clicks})...")
                
                # Try different possible selectors for Load More button
                load_more_selectors = [
                    "button:has-text('Load More')",
                    "button:has-text('load more')",
                    "button:has-text('LOAD MORE')",
                    "a:has-text('Load More')",
                    "a:has-text('load more')",
                    "a:has-text('LOAD MORE')",
                    "[data-testid*='load']",
                    "[class*='load']",
                    "button[class*='more']",
                    "a[class*='more']"
                ]
                
                load_more_clicked = False
                for selector in load_more_selectors:
                    load_more_button = page.locator(selector).first
                    if load_more_button.count() > 0:
                        try:
                            # Scroll to the button first
                            load_more_button.scroll_into_view_if_needed()
                            page.wait_for_timeout(1000)
                            
                            # Click the button
                            load_more_button.click()
                            load_more_clicked = True
                            print(f"✅ Load More button clicked using selector: {selector}")
                            
                            # Wait for new content to load
                            page.wait_for_timeout(3000)
                            break
                        except Exception as e:
                            print(f"❌ Failed to click Load More with selector {selector}: {e}")
                            continue
                
                if not load_more_clicked:
                    print(f"⚠️ Could not find or click Load More button on attempt {click_count}")
                    # Try scrolling to bottom to trigger lazy loading
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
            
            # Collect all vehicle links after each load
            print(f"📊 Collecting vehicle links (attempt {click_count + 1})...")
            
            # All <a> tags inside section
            a_tags = page.locator('#comp-lp1o159y a')
            count = a_tags.count()
            
            current_links = 0
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
                    
                    if href not in vehicle_links:
                        vehicle_links.add(href)
                        current_links += 1
            
            total_links = len(vehicle_links)
            print(f"🔍 Found {current_links} new links, total: {total_links}")
            
            # If no new links were added, we might have reached the end
            if click_count > 0 and current_links == 0:
                print("⚠️ No new links found, might have reached the end of available vehicles")
                break
        
        return list(vehicle_links)
    
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
            # Get all vehicle links with Load More functionality
            print("🔍 Getting vehicle links from the market page...")
            print("🔄 Will click 'Load More' button 5 times to get more vehicles...")
            vehicle_links = get_vehicle_links(page, load_more_clicks=5)
            
            if not vehicle_links:
                print("❌ No vehicle links found!")
                return
            
            print(f"🚗 Found {len(vehicle_links)} total vehicle links after loading more content")
            
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