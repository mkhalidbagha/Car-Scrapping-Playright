import json
import time
import re
import asyncio
import csv
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page, BrowserContext


class ImprovedClassicValuerScraper:
    """
    Improved Python Playwright scraper for TheClassicValuer.com market page.
    Focuses on accurate data extraction and proper HTML parsing.
    Now saves data in CSV format.
    """
    
    def __init__(self, options: Dict = None):
        """Initialize the scraper with configuration options."""
        self.browser = None
        self.context = None
        self.page = None
        self.base_url = 'https://www.theclassicvaluer.com'
        self.market_url = f'{self.base_url}/the-market'
        
        # Default options
        default_options = {
            'headless': False,
            'timeout': 30000,
            'delay': 3000,
            'output_file': 'classic_valuer_improved.csv',
            'max_pages': 5,
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        self.options = {**default_options, **(options or {})}
        self.results = []
        
        # CSV column headers
        self.csv_headers = [
            'make', 'model', 'production_year', 'date_of_sale', 'sold_price',
            'manual_gearbox', 'description', 'auction_house', 'country_of_sale',
            'spyder'
        ]
        
    async def init(self):
        """Initialize the browser and create a new page."""
        try:
            print('Launching browser...')
            playwright = await async_playwright().start()
            
            self.browser = await playwright.chromium.launch(
                headless=self.options['headless'],
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            self.context = await self.browser.new_context(
                viewport=self.options['viewport'],
                user_agent=self.options['user_agent']
            )
            
            self.page = await self.context.new_page()
            self.page.set_default_timeout(self.options['timeout'])
            
            print('Browser initialized successfully')
            
        except Exception as error:
            print(f'Failed to initialize browser: {error}')
            raise error

    async def navigate_to_market(self) -> bool:
        """Navigate to the market page with error handling."""
        try:
            print(f'Navigating to: {self.market_url}')
            await self.page.goto(self.market_url, wait_until='networkidle')
            await self.page.wait_for_timeout(self.options['delay'])
            
            # Wait for content to load
            await self.page.wait_for_selector('body', timeout=10000)
            
            return True
            
        except Exception as error:
            print(f'Failed to navigate: {error}')
            return False

    async def extract_listings_data(self) -> List[Dict]:
        """Extract vehicle listings using improved selectors and parsing."""
        try:
            print('Extracting vehicle listings...')
            
            # Wait for page content
            await self.page.wait_for_timeout(5000)
            
            # Get the page content and extract listings more intelligently
            listings = await self.page.evaluate('''
                () => {
                    const listings = [];
                    
                    // Look for common patterns in classic car auction sites
                    const selectors = [
                        '[class*="listing"]',
                        '[class*="vehicle"]', 
                        '[class*="car"]',
                        '[class*="item"]',
                        '[class*="result"]',
                        '[class*="card"]',
                        'article',
                        '.row',
                        '[data-*="vehicle"]'
                    ];
                    
                    let foundElements = [];
                    
                    // Try each selector
                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            foundElements = Array.from(elements);
                            console.log(`Found ${elements.length} elements with selector: ${selector}`);
                            break;
                        }
                    }
                    
                    // If no structured elements found, parse the main content differently
                    if (foundElements.length === 0) {
                        // Get all text content and split by common patterns
                        const bodyText = document.body.textContent || '';
                        
                        // Look for auction date patterns (27 Jul 2025, etc.)
                        const datePattern = /\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}/g;
                        const dateMatches = [...bodyText.matchAll(datePattern)];
                        
                        if (dateMatches.length > 0) {
                            dateMatches.forEach((match, index) => {
                                const startPos = match.index;
                                const endPos = index < dateMatches.length - 1 ? 
                                    dateMatches[index + 1].index : bodyText.length;
                                
                                const listingText = bodyText.substring(startPos, endPos).trim();
                                
                                if (listingText.length > 50) { // Only meaningful chunks
                                    listings.push({
                                        index: index,
                                        raw_text: listingText,
                                        extraction_method: 'date_pattern_split'
                                    });
                                }
                            });
                        }
                    } else {
                        // Process structured elements
                        foundElements.forEach((element, index) => {
                            const text = element.textContent?.trim() || '';
                            if (text.length > 20) { // Filter out small elements
                                listings.push({
                                    index: index,
                                    raw_text: text,
                                    html: element.innerHTML,
                                    extraction_method: 'structured_elements'
                                });
                            }
                        });
                    }
                    
                    return listings;
                }
            ''')
            
            print(f'Extracted {len(listings)} raw listings')
            return listings
            
        except Exception as error:
            print(f'Failed to extract listings: {error}')
            return []

    def process_vehicle_listings(self, raw_listings: List[Dict]) -> List[Dict]:
        """Process raw listings into structured vehicle data."""
        processed_listings = []
        seen_texts = set()  # Prevent duplicates
        
        for listing in raw_listings:
            try:
                text = listing.get('raw_text', '').strip()
                if not text or len(text) < 30:
                    continue
                
                # Skip duplicates
                text_hash = hash(text[:100])  # Hash first 100 chars
                if text_hash in seen_texts:
                    continue
                seen_texts.add(text_hash)
                
                # Extract vehicle information
                vehicle_data = self.parse_listing_text(text, listing.get('index', 0))
                
                # Only include listings with meaningful data
                if self.is_valid_vehicle_listing(vehicle_data):
                    processed_listings.append(vehicle_data)
                    
            except Exception as error:
                print(f'Error processing listing: {error}')
                continue
        
        # Remove duplicates based on combination of make, model, year, price
        unique_listings = []
        seen_vehicles = set()
        
        for listing in processed_listings:
            vehicle_key = (
                listing.get('make', '').lower(),
                listing.get('model', '').lower(), 
                listing.get('production_year', ''),
                listing.get('sold_price', '')
            )
            
            if vehicle_key not in seen_vehicles:
                seen_vehicles.add(vehicle_key)
                unique_listings.append(listing)
        
        print(f'Processed {len(unique_listings)} unique vehicle listings')
        return unique_listings

    def parse_listing_text(self, text: str, index: int) -> Dict:
        """Parse individual listing text to extract vehicle information."""
        
        # Extract auction date (typically at the start)
        date_match = re.search(r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})', text)
        auction_date = self.format_date(date_match.group(1)) if date_match else ''
        
        # Extract year (4 digits, prefer realistic car years)
        year_matches = re.findall(r'\b(19[3-9]\d|20[0-2]\d)\b', text)
        production_year = year_matches[0] if year_matches else ''
        
        # Extract make and model more accurately
        make_model = self.extract_make_model_improved(text)
        
        # Extract price ranges (£X,XXX - £X,XXX or £X,XXX)
        price_patterns = [
            r'£([\d,]+(?:\.\d{2})?)\s*-\s*£([\d,]+(?:\.\d{2})?)',  # Range
            r'£([\d,]+(?:\.\d{2})?)'  # Single price
        ]
        
        price = ''
        for pattern in price_patterns:
            price_match = re.search(pattern, text)
            if price_match:
                if len(price_match.groups()) == 2:  # Range
                    # Use midpoint of range
                    low = int(price_match.group(1).replace(',', ''))
                    high = int(price_match.group(2).replace(',', ''))
                    midpoint = int((low + high) / 2)
                    price = f'£{midpoint:,}'
                else:  # Single price
                    price = f"£{price_match.group(1)}"
                break
        
        # Check for transmission type
        manual_indicators = ['manual', 'stick', 'clutch', '5-speed', '6-speed', 'mt']
        auto_indicators = ['automatic', 'auto', 'tiptronic', 'dsg', 'cvt', 'paddle']
        
        text_lower = text.lower()
        has_manual = any(indicator in text_lower for indicator in manual_indicators)
        has_auto = any(indicator in text_lower for indicator in auto_indicators)
        
        # If both or neither found, default to unknown (False)
        manual_gearbox = has_manual and not has_auto
        
        # Check for Spyder/Spider variants
        is_spyder = bool(re.search(r'\b(?:spyder|spider)\b', text, re.IGNORECASE))
        
        # Extract country (look for "UK", "US", country names)
        country = self.extract_country_improved(text)
        
        # Extract auction house
        auction_house = self.extract_auction_house_improved(text)
        
        # Create clean description
        description = self.clean_description_text(text)
        
        return {
            'make': make_model['make'],
            'model': make_model['model'],
            'production_year': production_year,
            'date_of_sale': auction_date,
            'sold_price': price,
            'manual_gearbox': manual_gearbox,
            'description': description,
            'auction_house': auction_house,
            'country_of_sale': country,
            'spyder': is_spyder,
        }

    def extract_make_model_improved(self, text: str) -> Dict[str, str]:
        """Improved make and model extraction."""
        
        # Updated list of car makes with better patterns
        makes = [
            'Aston Martin', 'Alfa Romeo', 'Austin Healey', 'AC Cobra',
            'Ferrari', 'Porsche', 'Lamborghini', 'Maserati', 'McLaren',
            'Jaguar', 'Mercedes-Benz', 'Mercedes', 'BMW', 'Audi', 
            'Bentley', 'Rolls-Royce', 'Rolls Royce', 'Lotus', 'TVR',
            'MG', 'Triumph', 'Austin', 'Morris', 'Riley', 'Healey',
            'Ford', 'Chevrolet', 'Dodge', 'Plymouth', 'Pontiac',
            'Cadillac', 'Buick', 'Oldsmobile', 'Lincoln',
            'Volkswagen', 'VW', 'Peugeot', 'Renault', 'Citroën', 'Citroën',
            'Fiat', 'Lancia', 'Volvo', 'Saab', 'MINI', 'Mini',
            'Land Rover', 'Range Rover', 'Jeep', 'Toyota', 'Nissan',
            'Honda', 'Mazda', 'Subaru', 'Mitsubishi', 'Datsun'
        ]
        
        # Sort by length to match longer names first
        makes_sorted = sorted(makes, key=len, reverse=True)
        
        make = ''
        model = ''
        
        for make_name in makes_sorted:
            # Create a more flexible pattern
            pattern = rf'\b{re.escape(make_name)}\b'
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                make = make_name
                
                # Extract model: look for words after the make name
                make_pos = match.end()
                after_make = text[make_pos:].strip()
                
                # Find model words (excluding common non-model words)
                exclude_words = {
                    'auction', 'uk', 'estimate', 'sold', 'price', 'sale',
                    'condition', 'mileage', 'this', 'is', 'not', 'an',
                    'assessment', 'of', 'whether', 'vehicle', 'good', 'value'
                }
                
                model_words = []
                words = re.findall(r'\b[A-Za-z0-9\-]+\b', after_make)
                
                for word in words[:4]:  # Take up to 4 words
                    if word.lower() not in exclude_words and len(word) > 1:
                        model_words.append(word)
                    else:
                        break  # Stop at first excluded word
                
                model = ' '.join(model_words) if model_words else ''
                break
        
        return {'make': make, 'model': model}

    def extract_country_improved(self, text: str) -> str:
        """Improved country extraction."""
        country_patterns = [
            (r'\bUK\b', 'United Kingdom'),
            (r'\bUnited Kingdom\b', 'United Kingdom'),
            (r'\bUSA?\b', 'United States'),
            (r'\bUnited States\b', 'United States'),
            (r'\bFrance\b', 'France'),
            (r'\bGermany\b', 'Germany'),
            (r'\bItaly\b', 'Italy'),
            (r'\bJapan\b', 'Japan'),
            (r'\bAustralia\b', 'Australia'),
            (r'\bCanada\b', 'Canada')
        ]
        
        for pattern, country_name in country_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return country_name
        
        return ''

    def extract_auction_house_improved(self, text: str) -> str:
        """Improved auction house extraction."""
        auction_houses = [
            'Barrett-Jackson', 'RM Sotheby\'s', 'RM Sothebys', 'Bonhams',
            'Christie\'s', 'Gooding & Company', 'Mecum', 'Artcurial',
            'Coys', 'H&H', 'Silverstone Auctions', 'Historics',
            'Collecting Cars', 'Bring a Trailer', 'BaT', 'Cars & Bids'
        ]
        
        text_lower = text.lower()
        for house in auction_houses:
            if house.lower() in text_lower:
                return house
        
        return ''

    def clean_description_text(self, text: str) -> str:
        """Clean and format description text."""
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common boilerplate text
        boilerplate_patterns = [
            r'This is not an assessment of whether a vehicle is good value.*?recent sales\.?',
            r'Rather, how the sale price or estimate mid-point compares to recent sales\.?',
            r'Estimate\s*',
            r'Auction\s*•\s*UK\s*'
        ]
        
        for pattern in boilerplate_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        # Limit length
        if len(cleaned) > 300:
            cleaned = cleaned[:300] + '...'
        
        return cleaned.strip()

    def format_date(self, date_str: str) -> str:
        """Convert date string to DD/MM/YYYY format."""
        try:
            # Handle "27 Jul 2025" format
            if re.match(r'\d{1,2}\s+[A-Za-z]{3}\s+\d{4}', date_str):
                from datetime import datetime
                parsed_date = datetime.strptime(date_str, '%d %b %Y')
                return parsed_date.strftime('%d/%m/%Y')
        except:
            pass
        
        return date_str

    def is_valid_vehicle_listing(self, vehicle_data: Dict) -> bool:
        """Check if a listing contains valid vehicle data."""
        has_make_or_model = bool(vehicle_data.get('make') or vehicle_data.get('model'))
        has_year = bool(vehicle_data.get('production_year'))
        has_price = bool(vehicle_data.get('sold_price'))
        has_meaningful_description = len(vehicle_data.get('description', '').strip()) > 20
        
        # Must have at least 2 of these criteria
        criteria_met = sum([has_make_or_model, has_year, has_price, has_meaningful_description])
        return criteria_met >= 2

    async def scrape_market_data(self) -> List[Dict]:
        """Main scraping method."""
        try:
            if not await self.navigate_to_market():
                return []
            
            all_listings = []
            page_count = 0
            
            while page_count < self.options['max_pages']:
                print(f'Processing page {page_count + 1}...')
                
                # Extract listings from current page
                raw_listings = await self.extract_listings_data()
                
                if not raw_listings:
                    print('No more listings found')
                    break
                
                # Process the listings
                processed_listings = self.process_vehicle_listings(raw_listings)
                all_listings.extend(processed_listings)
                
                print(f'Found {len(processed_listings)} valid listings on page {page_count + 1}')
                
                # Try to navigate to next page (if pagination exists)
                has_next_page = await self.navigate_to_next_page()
                if not has_next_page:
                    print('No more pages available')
                    break
                
                page_count += 1
                await self.page.wait_for_timeout(self.options['delay'])
            
            print(f'Total unique listings found: {len(all_listings)}')
            return all_listings
            
        except Exception as error:
            print(f'Error during scraping: {error}')
            return []

    async def navigate_to_next_page(self) -> bool:
        """Try to navigate to the next page of results."""
        try:
            # Look for pagination controls
            next_selectors = [
                'a[href*="page"]:has-text("Next")',
                'button:has-text("Next")',
                '.pagination .next',
                '[data-page="next"]',
                'a:has-text(">")'
            ]
            
            for selector in next_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        print(f'Clicking next page: {selector}')
                        await element.click()
                        await self.page.wait_for_timeout(3000)
                        return True
                except:
                    continue
            
            return False
            
        except Exception as error:
            print(f'Error navigating to next page: {error}')
            return False

    async def save_results_csv(self, listings: List[Dict]) -> str:
        """Save results to CSV file."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'classic_valuer_improved.csv'
            
            # Ensure all listings have all required fields
            for listing in listings:
                for header in self.csv_headers:
                    if header not in listing:
                        listing[header] = ''
            
            # Write CSV file
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
                
                # Write header row
                writer.writeheader()
                
                # Write data rows
                for listing in listings:
                    # Clean data for CSV (remove newlines and commas that might break formatting)
                    cleaned_listing = {}
                    for key, value in listing.items():
                        if isinstance(value, str):
                            # Replace newlines and excessive commas
                            cleaned_value = value.replace('\n', ' ').replace('\r', ' ')
                            cleaned_value = re.sub(r'\s+', ' ', cleaned_value).strip()
                            cleaned_listing[key] = cleaned_value
                        else:
                            cleaned_listing[key] = value
                    
                    writer.writerow(cleaned_listing)

            print(f'Results saved to CSV: {filename}')
            return filename

        except Exception as error:
            print(f'Failed to save CSV results: {error}')
            raise error

    async def save_results_json_backup(self, listings: List[Dict]) -> str:
        """Save results to JSON file as backup."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'classic_valuer_backup_{timestamp}.json'
            
            output_data = {
                'metadata': {
                    'scraped_at': datetime.now().isoformat(),
                    'total_records': len(listings),
                    'source': 'theclassicvaluer.com/the-market',
                    'scraper_version': '3.0_improved_csv',
                    'extraction_notes': 'Improved parsing and deduplication - CSV output'
                },
                'results': listings
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            print(f'Backup JSON saved: {filename}')
            return filename

        except Exception as error:
            print(f'Failed to save JSON backup: {error}')
            return ''

    async def close(self):
        """Close browser and cleanup resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        print('Browser closed')

    async def scrape(self) -> Dict:
        """Main scraping entry point."""
        try:
            await self.init()
            listings = await self.scrape_market_data()
            
            if listings:
                # Save to CSV (primary output)
                csv_filename = await self.save_results_csv(listings)
                
                
                return {
                    'success': True,
                    'records_found': len(listings),
                    'csv_file': csv_filename,
                    'results': listings[:10]  # Return first 10 for preview
                }
            else:
                return {
                    'success': False,
                    'error': 'No valid listings found',
                    'records_found': 0
                }

        except Exception as error:
            print(f'Scraping failed: {error}')
            return {
                'success': False,
                'error': str(error),
                'records_found': 0
            }
        finally:
            await self.close()


# Usage functions
async def run_improved_scraper():
    """Run the improved scraper with CSV output."""
    scraper = ImprovedClassicValuerScraper({
        'headless': False,  # Set to True for production
        'timeout': 30000,
        'delay': 3000,
        'max_pages': 3
    })

    result = await scraper.scrape()
    
    if result['success']:
        print(f'\n✅ Scraping completed successfully!')
        print(f'📊 Records found: {result["records_found"]}')
        print(f'📄 CSV file: {result["csv_file"]}')
        if result.get('json_backup'):
            print(f'💾 JSON backup: {result["json_backup"]}')
        
        # Print sample results
        if result.get('results'):
            print('\n📋 Sample listings:')
            for i, listing in enumerate(result['results'][:5]):
                make = listing.get('make', 'Unknown')
                model = listing.get('model', 'Unknown')
                year = listing.get('production_year', 'Unknown')
                price = listing.get('sold_price', 'No price')
                print(f'{i+1}. {year} {make} {model} - {price}')
                
    else:
        print(f'\n❌ Scraping failed: {result["error"]}')

    return result


def scrape_market_improved(options: Dict = None):
    """Synchronous wrapper for the improved scraper."""
    return asyncio.run(run_improved_scraper())


if __name__ == '__main__':
    print("🚗 Starting Improved Classic Valuer Market Scraper (CSV Output)...")
    result = asyncio.run(run_improved_scraper())