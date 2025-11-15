from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import time
import re

def extract_number(text):
    """Extract numeric value from text"""
    if not text:
        return None
    match = re.search(r'[\d.]+', text)
    return float(match.group()) if match else None

def parse_listing(article):
    """Parse a single listing article element"""
    try:
        # Extract Property ID
        id_elem = article.query_selector('div.listing-address p:first-child')
        property_id = id_elem.inner_text().strip().replace(' •', '') if id_elem else None
        
        # Extract Title
        title_elem = article.query_selector('h3 a.listing-name')
        title = title_elem.get_attribute('title') if title_elem else None
        url = title_elem.get_attribute('href') if title_elem else None
        
        # Extract Price
        price_elem = article.query_selector('div.listing-price a.listing-price-link')
        price_text = price_elem.inner_text().strip() if price_elem else None
        price = None
        if price_text:
            # Remove "tỷ" and "VND" to get numeric value
            price = extract_number(price_text.replace('tỷ', '').replace('VND', ''))
        
        # Extract Address components
        address_parts = []
        address_elems = article.query_selector_all('div.listing-address p a')
        for elem in address_elems:
            text = elem.inner_text().strip()
            if text:
                address_parts.append(text)
        address = ' '.join(address_parts) if address_parts else None
        
        # Extract info list (bedrooms, bathrooms, area, direction)
        info_items = article.query_selector_all('ul.listing-info li')
        bedrooms = None
        bathrooms = None
        area = None
        direction = None
        
        for item in info_items:
            text = item.inner_text().strip()
            icon_class = item.query_selector('i')
            
            if icon_class:
                class_name = icon_class.get_attribute('class')
                
                # Bedrooms (airline-seat icon)
                if 'zmdi-airline-seat-individual-suite' in class_name:
                    bedrooms = extract_number(text)
                
                # Bathrooms (bath-room icon)
                elif 'icon-bath-room' in class_name:
                    bathrooms = extract_number(text)
                
                # Area (square icon)
                elif 'zmdi-photo-size-select-small' in class_name:
                    area = extract_number(text.replace('m²', '').strip())
                
                # Direction (compass icon)
                elif 'zmdi-compass' in class_name:
                    direction = text.strip()
        
        # Calculate price per m2 (in million)
        price_per_m2 = None
        if price and area:
            price_per_m2 = round((price * 1000) / area, 2)  # Convert billion to million, then divide by area
        
        return {
            'ID tin': property_id,
            'Tiêu đề': title,
            'Giá (tỷ)': price,
            'Diện tích (m²)': area,
            'PN': int(bedrooms) if bedrooms else None,
            'WC': int(bathrooms) if bathrooms else None,
            'Địa chỉ': address,
            'Hướng': direction,
            'Link': url,
            'Giá/m² (triệu)': price_per_m2
        }
    except Exception as e:
        print(f"Error parsing listing: {e}")
        return None

def crawl_page(page, page_num):
    """Crawl a single page"""
    url = f"https://rever.vn/s/ho-chi-minh/mua/can-ho?page={page_num}"
    print(f"Crawling page {page_num}: {url}")
    
    try:
        # Navigate to page
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        
        # Wait for listings to load
        page.wait_for_selector('article.box.listView', timeout=15000)
        time.sleep(2)  # Additional wait for dynamic content
        
        # Get all listing articles
        articles = page.query_selector_all('article.box.listView')
        print(f"  Found {len(articles)} listings on page {page_num}")
        
        # Parse each listing
        listings = []
        for article in articles:
            listing_data = parse_listing(article)
            if listing_data:
                listings.append(listing_data)
        
        return listings
    
    except Exception as e:
        print(f"  ERROR on page {page_num}: {e}")
        return []

def main():
    print("Starting crawl of 30 pages from rever.vn...")
    print("=" * 80)
    
    all_listings = []
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        # Crawl pages 1-30
        for page_num in range(1, 31):
            listings = crawl_page(page, page_num)
            all_listings.extend(listings)
            
            # Progress update
            print(f"  Total listings collected so far: {len(all_listings)}")
            print("-" * 80)
            
            # Small delay between pages
            time.sleep(1)
        
        # Close browser
        browser.close()
    
    # Create DataFrame
    print("\nCreating DataFrame...")
    df = pd.DataFrame(all_listings)
    
    # Add STT (sequential number)
    df.insert(0, 'STT', range(1, len(df) + 1))
    
    # Reorder columns
    column_order = ['STT', 'ID tin', 'Tiêu đề', 'Giá (tỷ)', 'Diện tích (m²)', 
                    'PN', 'WC', 'Địa chỉ', 'Hướng', 'Link', 'Giá/m² (triệu)']
    df = df[column_order]
    
    # Save to CSV
    timestamp = datetime.now().strftime('%d%m%Y_%H%M')
    filename = f'rever_hcm_30pages_{timestamp}.csv'
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    
    # Print summary
    print("=" * 80)
    print("CRAWL COMPLETED!")
    print(f"Total listings collected: {len(df)}")
    print(f"Saved to: {filename}")
    print("\nData preview:")
    print(df.head(10).to_string())
    print("\nData summary:")
    print(df.info())
    print("\nPrice statistics:")
    print(df['Giá (tỷ)'].describe())

if __name__ == "__main__":
    main()
