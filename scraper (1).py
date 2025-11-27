"""
Scraper functions for StreetEasy
Contains all web scraping and data extraction logic using ScrapingBee
"""

import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urlencode
import streamlit as st
from datetime import datetime, timedelta
from constants import AREA_IDS, PROPERTY_TYPE_CODES

def get_area_ids(neighborhoods):
    """Convert neighborhood names to area IDs"""
    area_map = AREA_IDS

    if neighborhoods and len(neighborhoods) > 0:
        return [area_map[name] for name in neighborhoods if name in area_map]
    else:
        return list(area_map.values())


@st.cache_data(ttl='24hr')
def build_search_url(max_price, property_type, max_taxes, max_fees, neighborhoods=None, min_sqft=None):
    """Build StreetEasy search URL with filters matching their actual format"""
    base_url = "https://streeteasy.com/for-sale/nyc"
    
    # Build filter components
    filters = []
    
    # Property type
    type_code = PROPERTY_TYPE_CODES.get(property_type)
    if type_code:
        filters.append(f"type:{type_code}")
    
    # Price filter
    if max_price and max_price > 0:
        filters.append(f"price:-{int(max_price)}")
    
    # Min sqft filter
    if min_sqft and min_sqft > 0:
        filters.append(f"sqft>={int(min_sqft)}")
    
    # Area IDs (neighborhoods)
    area_ids = get_area_ids(neighborhoods)
    if len(area_ids) > 0:        
        area_str = ",".join(map(str, area_ids))
        filters.append(f"area:{area_str}")
    else:
        filters.append(f"area:101")
    
    # Monthly maintenance/fees
    if max_fees and max_fees > 0:
        filters.append(f"maintenance<={int(max_fees)}")
    
    # Monthly taxes
    if max_taxes and max_taxes > 0:
        filters.append(f"taxes<={int(max_taxes)}")
    
    # Combine filters with pipe separator
    if filters:
        filter_str = "|".join(filters)
        url = f"{base_url}/{filter_str}"
    else:
        url = base_url
    
    # Add sorting
    url += "?sort_by=listed_desc"
    
    return url


def scrape_with_scrapingbee(url, api_key, render_js=False):
    """
    Make a request using ScrapingBee API
    
    Args:
        url: Target URL to scrape
        api_key: ScrapingBee API key
        render_js: Whether to render JavaScript (costs 5 credits vs 1)
    
    Returns:
        Response object from ScrapingBee
    """
    scrapingbee_url = "https://app.scrapingbee.com/api/v1/"
    
    params = {
        'api_key': api_key,
        'url': url,
        'render_js': 'true' if render_js else 'false',
        'premium_proxy': 'false',  # Set to 'true' if you need residential proxies (10 credits)
        'country_code': 'us',
    }
    
    response = requests.get(scrapingbee_url, params=params, timeout=90)
    
    # Increment API call counter
    if 'api_calls' not in st.session_state:
        st.session_state.api_calls = 0
    st.session_state.api_calls += 1
    
    # Track credits used (1 for standard, 5 for JS rendering)
    if 'api_credits' not in st.session_state:
        st.session_state.api_credits = 0
    st.session_state.api_credits += (5 if render_js else 1)
    
    response.raise_for_status()
    return response


def extract_number(text):
    """Extract numeric value from text"""
    if not text:
        return None
    cleaned = text.replace('$', '').replace(',', '').replace('/mo', '').replace('/month', '').strip()
    match = re.search(r'\d+', cleaned)
    return int(match.group()) if match else None


def parse_listing_date(date_str):
    """Parse listing date string to datetime object"""
    if not date_str:
        return None
    
    try:
        date_str = date_str.strip()
        
        date_formats = [
            '%m/%d/%Y',
            '%m-%d-%Y',
            '%Y-%m-%d',
            '%B %d, %Y',
            '%b %d, %Y',
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    except Exception:
        return None


def calculate_listing_date_from_days(days_on_market):
    """Calculate listing date from days on market"""
    if not days_on_market or days_on_market < 0:
        return None
    
    try:
        current_date = datetime.now()
        listing_date = current_date - timedelta(days=days_on_market)
        return listing_date
    except Exception:
        return None


@st.cache_data(ttl='24hr')
def scrape_listing_details(listing_url, api_key):
    """Scrape detailed info from individual listing page using ScrapingBee"""
    try:
        response = scrape_with_scrapingbee(listing_url, api_key, render_js=False)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        details = {}
        
        # Get all text for searching
        page_text = soup.get_text(separator=' ', strip=True)
        
        # Look for structured data elements
        detail_sections = soup.find_all(['div', 'section', 'dl', 'ul'], 
                                       class_=re.compile(r'detail|info|stat|fact', re.I))
        
        combined_text = page_text
        if detail_sections:
            combined_text += " " + " ".join([section.get_text(separator=' ', strip=True) 
                                            for section in detail_sections])
        
        # Extract listing date
        date_patterns = [
            r'Sales?\s+start\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',
            r'Listed\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',
            r'List(?:ing)?\s+date\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',
            r'(?:On\s+market|Listed)\s+(?:since|on)\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, combined_text, re.I)
            if match:
                date_str = match.group(1)
                parsed_date = parse_listing_date(date_str)
                if parsed_date:
                    details['listing_date'] = parsed_date
                    break
        
        # If no direct date found, try days on market
        if 'listing_date' not in details or details['listing_date'] is None:
            days_patterns = [
                r'Days?\s+on\s+market\s*:?\s*(\d+)\s*days?',
                r'(\d+)\s*days?\s+on\s+market',
                r'Listed\s+for\s+(\d+)\s*days?',
                r'On\s+market\s+for\s+(\d+)\s*days?',
            ]
            
            for pattern in days_patterns:
                match = re.search(pattern, combined_text, re.I)
                if match:
                    days = int(match.group(1))
                    calculated_date = calculate_listing_date_from_days(days)
                    if calculated_date:
                        details['listing_date'] = calculated_date
                        details['days_on_market'] = days
                        break
        
        # Extract square footage
        sqft_patterns = [
            r'(\d[\d,]+)\s*sq\.?\s*f(?:ee)?t',
            r'(\d[\d,]+)\s*sqft',
            r'(\d[\d,]+)\s*SF\b',
            r'(?:interior|size)\s*:?\s*(\d[\d,]+)',
            r'approx\.?\s*(\d[\d,]+)\s*sq',
            r'(\d[\d,]+)\s*square\s*feet',
            r'total\s*:?\s*(\d[\d,]+)\s*sq',
            r'area\s*:?\s*(\d[\d,]+)\s*sq',
            r'(\d[\d,]+)\s*ft(?:\u00B2|²)'
        ]
        for pattern in sqft_patterns:
            match = re.search(pattern, combined_text, re.I)
            if match:
                sqft_val = extract_number(match.group(1))
                if sqft_val and 200 <= sqft_val <= 10000:
                    details['sqft'] = sqft_val
                    break
        
        # Extract monthly taxes
        tax_patterns = [
            r'monthly\s*taxes?\s*:?\s*\$?([\d,]+)',
            r'taxes?\s*\(?monthly\)?\s*:?\s*\$?([\d,]+)',
            r'taxes?\s*:?\s*\$?([\d,]+)\s*/?mo',
            r'taxes?\s*:?\s*\$?([\d,]+)\s*per\s*month',
            r'\$?([\d,]+)\s*/?mo\s*taxes?',
            r'property\s*tax\s*:?\s*\$?([\d,]+)',
            r'tax\s*:?\s*\$?([\d,]+)\s*monthly',
        ]
        for pattern in tax_patterns:
            match = re.search(pattern, combined_text, re.I)
            if match:
                tax_val = extract_number(match.group(1))
                if tax_val and 0 < tax_val < 50000:
                    details['taxes'] = tax_val
                    break
        
        # Extract common charges/HOA fees
        fee_patterns = [
            r'common\s*charges?\s*:?\s*\$?([\d,]+)',
            r'maintenance\s*:?\s*\$?([\d,]+)',
            r'HOA\s*(?:fees?)?\s*:?\s*\$?([\d,]+)',
            r'monthly\s*(?:common\s*)?charges?\s*:?\s*\$?([\d,]+)',
            r'\$?([\d,]+)\s*/?mo\s*(?:common|maint|CC)',
            r'CC\s*:?\s*\$?([\d,]+)',
            r'common\s*:?\s*\$?([\d,]+)\s*/?mo',
            r'maint\.?\s*:?\s*\$?([\d,]+)\s*/?mo',
        ]
        for pattern in fee_patterns:
            match = re.search(pattern, combined_text, re.I)
            if match:
                fee_val = extract_number(match.group(1))
                if fee_val and 0 < fee_val < 20000:
                    details['fees'] = fee_val
                    break
        
        return details
        
    except Exception as e:
        return {}


@st.cache_data(ttl='24hr', show_spinner=False)  
def scrape_streeteasy(url, api_key, scrape_details=False, max_pages=5):
    """Scrape StreetEasy listings with pagination support using ScrapingBee"""
    all_listings = []
    
    for page_num in range(1, max_pages + 1):
        # Build URL with page parameter
        if '?' in url:
            page_url = f"{url}&page={page_num}"
        else:
            page_url = f"{url}?page={page_num}"
        
        try:
            response = scrape_with_scrapingbee(page_url, api_key, render_js=False)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find listing cards
            listing_cards = []
            
            selectors = [
                {'name': 'div', 'attrs': {'class': re.compile(r'listingCard', re.I)}},
                {'name': 'article', 'attrs': {'class': re.compile(r'listing|card', re.I)}},
            ]
            
            for selector in selectors:
                cards = soup.find_all(selector['name'], selector['attrs'])
                if cards:
                    listing_cards = cards
                    break
            
            if not listing_cards:
                break
            
            # Parse each listing card
            page_listings = []
            for card in listing_cards:
                try:
                    listing = {
                        'address': None,
                        'neighborhood': None,
                        'price': None,
                        'sqft': None,
                        'taxes': None,
                        'fees': None,
                        'listing_date': None,
                        'days_on_market': None,
                        'url': None
                    }
                    
                    # Extract URL
                    link = card.find('a', href=re.compile(r'/sale/\d+'))
                    if not link:
                        link = card.find('a', href=re.compile(r'/building/'))
                    if not link:
                        link = card.find('a', href=True)
                    
                    if link:
                        href = link.get('href')
                        if href:
                            listing['url'] = f"https://streeteasy.com{href}" if href.startswith('/') else href
                    
                    # Extract text content
                    card_text = card.get_text(separator='|', strip=True)
                    
                    # Extract address
                    address_elem = (
                        card.find('a', class_=re.compile(r'address|title|listingCard', re.I)) or
                        card.find(['h3', 'h4', 'h5'], class_=re.compile(r'address|title', re.I)) or
                        card.find('address')
                    )
                    if address_elem:
                        listing['address'] = address_elem.get_text(strip=True)

                    # Extract neighborhood
                    neighborhood_elem = card.find('p', class_=re.compile(r'ListingDescription-module__title', re.I))
                    if neighborhood_elem:
                        text = neighborhood_elem.get_text(" ", strip=True)
                        match = re.search(r'in\s+(.*)', text, re.I)
                        listing['neighborhood'] = match.group(1).strip() if match else None
                    
                    # Extract price
                    price_elem = card.find(['span', 'div'], class_=re.compile(r'price', re.I))
                    if price_elem:
                        text = price_elem.get_text(" ", strip=True)
                        listing['price'] = extract_number(text)
                    else:
                        price_match = re.search(r'\$\s*[\d,]+', card_text)
                        if price_match:
                            listing['price'] = extract_number(price_match.group())
                    
                    # Extract square footage
                    sqft_patterns = [
                        r'(\d[\d,]*)\s*sq\.?\s*ft',
                        r'(\d[\d,]*)\s*sqft',
                        r'(\d[\d,]*)\s*SF',
                    ]
                    for pattern in sqft_patterns:
                        sqft_match = re.search(pattern, card_text, re.I)
                        if sqft_match:
                            listing['sqft'] = extract_number(sqft_match.group(1))
                            break
                    
                    # Extract taxes
                    tax_patterns = [
                        r'taxes?\s*[:\-]?\s*\$?([\d,]+)(?:/mo|/month)?',
                        r'\$?([\d,]+)\s*(?:/mo|/month)?\s*taxes?',
                    ]
                    for pattern in tax_patterns:
                        tax_match = re.search(pattern, card_text, re.I)
                        if tax_match:
                            listing['taxes'] = extract_number(tax_match.group(1))
                            break
                    
                    # Extract common charges/fees
                    fee_patterns = [
                        r'common charges?\s*[:\-]?\s*\$?([\d,]+)(?:/mo)?',
                        r'maint(?:enance)?\s*[:\-]?\s*\$?([\d,]+)(?:/mo)?',
                    ]
                    for pattern in fee_patterns:
                        fee_match = re.search(pattern, card_text, re.I)
                        if fee_match:
                            listing['fees'] = extract_number(fee_match.group(1))
                            break
                    
                    if listing['url'] or listing['address']:
                        page_listings.append(listing)
                        
                except Exception:
                    continue
            
            # Add page listings to all listings
            all_listings.extend(page_listings)
            
            # Rate limiting between pages
            if page_num < max_pages:
                time.sleep(1)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                st.error("⛔ Access forbidden (403). Check your ScrapingBee credits or API key.")
            else:
                st.error(f"HTTP Error: {str(e)}")
            break
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            break
    
    # Remove duplicates based on URL or address
    seen_urls = set()
    seen_addresses = set()
    unique_listings = []
    
    for listing in all_listings:
        if listing['url']:
            if listing['url'] not in seen_urls:
                seen_urls.add(listing['url'])
                unique_listings.append(listing)
        elif listing['address']:
            if listing['address'] not in seen_addresses:
                seen_addresses.add(listing['address'])
                unique_listings.append(listing)
    
    listings = unique_listings
    
    # Scrape detailed info for all listings
    if scrape_details and listings:
        progress_bar = st.progress(0, text=f"Fetching details for {len(listings)} listings...")
        
        for i, listing in enumerate(listings):
            if listing['url']:
                details = scrape_listing_details(listing['url'], api_key)
                
                # Update with detailed info
                if details.get('sqft'):
                    listing['sqft'] = details['sqft']
                if details.get('taxes'):
                    listing['taxes'] = details['taxes']
                if details.get('fees'):
                    listing['fees'] = details['fees']
                if details.get('listing_date'):
                    listing['listing_date'] = details['listing_date']
                if details.get('days_on_market'):
                    listing['days_on_market'] = details['days_on_market']
                    
                # Calculate days_on_market if listing_date is known but DOM is not
                if listing['listing_date'] and not listing['days_on_market']:
                    time_difference = datetime.now() - listing['listing_date']
                    listing['days_on_market'] = time_difference.days
                
                # Update progress
                progress_bar.progress((i + 1) / len(listings), 
                                     text=f"Fetching details: {i+1}/{len(listings)}")
                time.sleep(1)  # Rate limiting
        
        progress_bar.empty()
    
    return listings
