# Main NiceGUI application for the StreetEasy NYC Sales Scraper

import asyncio
import pandas as pd
from nicegui import ui, app
import time
from typing import Dict, Any, List

# --- MOCK DEPENDENCIES (REPLACE WITH YOUR ACTUAL FILES) ---
# NOTE: To run this successfully, you must have your actual 'constants',
# 'scraper', and 'viz' modules in the same directory.
# The following code provides basic mock implementations for demonstration.

# Mock constants
NEIGHBORHOODS = ["Williamsburg", "Park Slope", "DUMBO", "Upper East Side", "Midtown"]
PROPERTY_TYPES = {"Condo": "condo", "Co-op": "coop", "House": "house"}
AREA_IDS = {"Williamsburg": 100, "Park Slope": 101, "Upper East Side": 300}

# Mock scraper and viz functions
def build_search_url(max_price, prop_type, max_taxes, max_fees, neighborhoods, min_sqft):
    """Mocks the URL builder."""
    base = "https://streeteasy.com/for-sale/"
    nb_names = ", ".join(neighborhoods) if neighborhoods else "All"
    return f"{base}?price-max={max_price}&type={prop_type}&taxes-max={max_taxes}&fees-max={max_fees}&sqft-min={min_sqft}&nb={nb_names}"

def scrape_streeteasy(search_url, api_key, scrape_details, max_pages):
    """Mocks the scraping process. In a real app, this would be blocking/async network IO."""
    print(f"MOCK: Scraping URL: {search_url} (Pages: {max_pages}, Details: {scrape_details})")
    time.sleep(2) # Simulate network delay
    
    # Simulate API call/credit update
    state.api_calls += max_pages + (5 if scrape_details else 0)
    state.api_credits += max_pages + (5 * 5 if scrape_details else 0)
    
    # Return mock data
    return [
        {'address': f'123 Main St, Unit {i}', 'neighborhood': NEIGHBORHOODS[i % len(NEIGHBORHOODS)], 
         'price': 850000 + i * 50000, 'sqft': 750 + i * 50, 
         'taxes': 1200 - i * 50, 'fees': 800 - i * 50, 
         'listing_date': f'2025-10-{20-i}', 'days_on_market': 5 + i * 2,
         'url': f'https://streeteasy.com/listing/{i}'}
        for i in range(10)
    ]

def create_all_visualizations(df: pd.DataFrame) -> Dict[str, Any]:
    """Mocks the visualization creator, returning placeholder Plotly figures."""
    import plotly.express as px
    
    # Simple mock plots
    vizs = {}
    
    # Use actual data for a more realistic mock
    if 'price' in df.columns:
        df['price_M'] = df['price'] / 1000000
        vizs['price_distribution'] = px.histogram(
            df, x='price_M', title='Price Distribution (Millions)', 
            labels={'price_M': 'Price ($M)'}, template='plotly_white'
        )
        vizs['neighborhood_comparison'] = px.box(
            df, x='neighborhood', y='price_M', title='Price by Neighborhood', 
            template='plotly_white'
        ).update_yaxes(title='Price ($M)')
    
    return vizs

# --- APPLICATION STATE MANAGEMENT ---

class AppState:
    """Class to hold all application state, similar to st.session_state."""
    def __init__(self):
        # API Metrics
        self.api_calls: int = 0
        self.api_credits: int = 0
        
        # Inputs
        self.scrapingbee_api_key: str = ""
        self.borough: str = "Brooklyn"
        self.use_preset: bool = False
        self.selected_neighborhoods: List[str] = []
        self.property_type: str = list(PROPERTY_TYPES.keys())[0]
        self.max_price: int = 900000
        self.min_sqft: int = 700
        self.max_taxes: int = 1500
        self.max_fees: int = 1000
        self.max_pages: int = 5
        self.scrape_details: bool = True
        self.is_loading: bool = False
        self.results_df: pd.DataFrame = pd.DataFrame()
        self.search_url: str = ""

state = AppState()

# --- UI COMPONENTS (Refreshable) ---

@ui.refreshable_app()
def api_metrics_row():
    """Displays the API usage metrics, only visible after the first search."""
    if state.api_calls > 0:
        with ui.row().classes('w-full justify-end items-center mb-4'):
            ui.label().classes('grow') # Spacer
            
            # Use NiceGUI 'badge' or 'metric' style layout
            with ui.row().classes('gap-6'):
                with ui.card.classes('p-2 shadow-lg w-36 bg-blue-100'):
                    ui.label('API Calls').classes('text-xs text-blue-800 font-semibold')
                    ui.label(f'{state.api_calls}').classes('text-xl font-bold text-blue-900')
                with ui.card.classes('p-2 shadow-lg w-36 bg-indigo-100'):
                    ui.label('Credits Used').classes('text-xs text-indigo-800 font-semibold')
                    ui.label(f'{state.api_credits}').classes('text-xl font-bold text-indigo-900')
                with ui.card.classes('p-2 shadow-lg w-36 bg-green-100'):
                    remaining = 1000 - state.api_credits
                    ui.label('Est. Remaining').classes('text-xs text-green-800 font-semibold')
                    ui.label(f'{remaining}/1000').classes('text-xl font-bold text-green-900')

            # Reset button
            ui.button("Reset Counters", on_click=reset_counters).classes('ml-6 self-center')
    else:
        # Placeholder to maintain space consistency
        ui.label().classes('h-10 w-full')

@ui.refreshable_app()
def results_display():
    """Displays the results section (data table and charts)."""
    if state.is_loading:
        with ui.row().classes('w-full justify-center py-12'):
            ui.spinner('dots', size='3em').props('color=primary')
            ui.label("Scraping StreetEasy with ScrapingBee...").classes('ml-3 text-lg text-primary')
        return

    if not state.results_df.empty:
        df = state.results_df.copy()
        num_listings = len(df)
        
        ui.notify(f"✅ Found {num_listings} listings!", type='positive')

        # --- Data Pre-processing for Display ---
        if 'listing_date' in df.columns:
            df['listing_date'] = pd.to_datetime(df['listing_date'], errors='coerce')
        
        if 'listing_date' in df.columns and df['listing_date'].notna().any():
            df = df.sort_values('listing_date', ascending=False)
            
        # Format columns for display
        display_df = df.copy()
        format_currency = lambda x: f"${x:,.0f}" if pd.notnull(x) and pd.api.types.is_numeric_dtype(x) else "N/A"
        format_sqft = lambda x: f"{x:,.0f}" if pd.notnull(x) and pd.api.types.is_numeric_dtype(x) else "N/A"
        format_date = lambda x: x.strftime('%b %d, %Y') if pd.notnull(x) and pd.api.types.is_datetime64_any_dtype(x) else "N/A"
        format_days = lambda x: f"{int(x)} days" if pd.notnull(x) and pd.api.types.is_numeric_dtype(x) else "N/A"
        
        for col in ['price']:
             if col in display_df.columns: display_df[col] = display_df[col].apply(format_currency)
        for col in ['taxes', 'fees']:
             if col in display_df.columns: display_df[col] = display_df[col].apply(format_currency)
        if 'sqft' in display_df.columns: display_df['sqft'] = display_df['sqft'].apply(format_sqft)
        if 'listing_date' in display_df.columns: display_df['listing_date'] = display_df['listing_date'].apply(format_date)
        if 'days_on_market' in display_df.columns: display_df['days_on_market'] = display_df['days_on_market'].apply(format_days)

        # AG Grid column definitions
        column_defs = [
            {'headerName': 'Address', 'field': 'address', 'width': 250},
            {'headerName': 'Neighborhood', 'field': 'neighborhood'},
            {'headerName': 'Price', 'field': 'price', 'type': 'numericColumn'},
            {'headerName': 'Sq Ft', 'field': 'sqft', 'type': 'numericColumn'},
            {'headerName': 'Monthly Taxes', 'field': 'taxes', 'type': 'numericColumn'},
            {'headerName': 'Monthly Fees', 'field': 'fees', 'type': 'numericColumn'},
            {'headerName': 'Listed Date', 'field': 'listing_date'},
            {'headerName': 'Days on Market', 'field': 'days_on_market', 'type': 'numericColumn'},
            {
                'headerName': 'URL', 'field': 'url', 'cellRenderer': 'LinkRenderer',
                'cellRendererParams': {'onClick': 'openLink'}, 'width': 100
            }
        ]
        
        # Link Renderer for AG Grid (NiceGUI specific)
        app.add_head_html("""
            <script>
                function openLink(params) {
                    if (params.data.url) {
                        window.open(params.data.url, '_blank');
                    }
                }
                var LinkRenderer = function(params) {
                    if (params.value) {
                        return '<a href="' + params.data.url + '" target="_blank">View</a>';
                    }
                    return '';
                };
            </script>
        """)
        
        with ui.tabs().classes('w-full') as tabs:
            tab1 = ui.tab('Data Table')
            tab2 = ui.tab('Visualizations')
        
        with ui.tab_panels(tabs, value=tab1).classes('w-full'):
            with ui.tab_panel(tab1):
                ui.aggrid({
                    'columnDefs': column_defs,
                    'rowData': display_df.to_dict('records'),
                    'defaultColDef': {'flex': 1, 'minWidth': 100, 'sortable': True, 'resizable': True},
                    'gridOptions': {'domLayout': 'autoHeight'},
                }).classes('h-96')
                
                # Download button
                csv_data = df.to_csv(index=False)
                ui.button('📥 Download CSV', on_click=lambda: ui.download(
                    csv_data, 
                    filename=f"streeteasy_{state.borough.lower()}_listings.csv", 
                    mime="text/csv"
                )).props('color=secondary').classes('mt-4')

            with ui.tab_panel(tab2):
                with ui.spinner('dots', size='lg'):
                    # Generate visualizations (can be computationally heavy, put inside spinner)
                    vizs = create_all_visualizations(df)
                    
                if not vizs:
                    ui.warning("Not enough data to create visualizations.")
                else:
                    # Display visualizations
                    
                    # Price Analysis (Side by side)
                    ui.label("Price Analysis").classes('text-xl font-bold mt-4')
                    with ui.row().classes('w-full'):
                        if 'price_distribution' in vizs:
                            ui.plotly(vizs['price_distribution']).classes('w-1/2')
                        if 'price_boxplot' in vizs:
                            ui.plotly(vizs['price_boxplot']).classes('w-1/2')

                    # Value Analysis (Full width)
                    if 'price_vs_sqft' in vizs:
                        ui.label("Value Analysis").classes('text-xl font-bold mt-4')
                        ui.plotly(vizs['price_vs_sqft']).classes('w-full')
                    if 'price_per_sqft' in vizs:
                        ui.plotly(vizs['price_per_sqft']).classes('w-full')
                        
                    # Monthly Costs (Side by side)
                    ui.label("Monthly Costs").classes('text-xl font-bold mt-4')
                    with ui.row().classes('w-full'):
                        if 'monthly_costs' in vizs:
                            ui.plotly(vizs['monthly_costs']).classes('w-1/2')
                        if 'total_cost_vs_price' in vizs:
                            ui.plotly(vizs['total_cost_vs_price']).classes('w-1/2')

                    # Comparison Plots (Full width)
                    if 'neighborhood_comparison' in vizs:
                        ui.label("Neighborhood Comparison").classes('text-xl font-bold mt-4')
                        ui.plotly(vizs['neighborhood_comparison']).classes('w-full')
                    
                    if 'affordability_heatmap' in vizs:
                        ui.label("Affordability Heatmap").classes('text-xl font-bold mt-4')
                        ui.plotly(vizs['affordability_heatmap']).classes('w-full')
    else:
        # Initial state or no results
        ui.info("👈 Set your filters in the sidebar and click 'Search Listings' to begin.")

# --- HANDLERS ---

async def search_listings():
    """Handler for the Search button."""
    if not state.scrapingbee_api_key:
        ui.notify("❌ Please enter your ScrapingBee API key in the sidebar", type='negative')
        return

    # Clear previous results and start loading
    state.results_df = pd.DataFrame()
    state.is_loading = True
    results_display.refresh()

    try:
        # 1. Build the search URL
        current_neighborhoods = get_selected_neighborhoods()
        state.search_url = build_search_url(
            state.max_price, 
            PROPERTY_TYPES[state.property_type], 
            state.max_taxes, 
            state.max_fees, 
            current_neighborhoods, 
            state.min_sqft
        )
        
        # 2. Run the scraping task in a separate thread/process to keep UI responsive
        listings = await ui.run_task(lambda: scrape_streeteasy(
            state.search_url, 
            state.scrapingbee_api_key, 
            state.scrape_details, 
            state.max_pages
        ))
        
        if listings:
            state.results_df = pd.DataFrame(listings)
            
        api_metrics_row.refresh()

    except Exception as e:
        ui.notify(f"An error occurred during scraping: {e}", type='negative', timeout=5000)
        state.results_df = pd.DataFrame()
    finally:
        state.is_loading = False
        results_display.refresh()
        
def reset_counters():
    """Resets API call counters."""
    state.api_calls = 0
    state.api_credits = 0
    api_metrics_row.refresh()
    
def get_selected_neighborhoods():
    """Determines the list of neighborhoods based on the preset toggle."""
    if state.use_preset:
        preset_ids = [102, 119, 135, 139, 303, 304, 307, 319, 324, 326, 340, 343, 355]
        # In a real app, you'd map IDs back to names
        combined_ids = {**AREA_IDS}
        id_to_name = {v: k for k, v in combined_ids.items()}
        preset_names = [id_to_name.get(id, f"Area {id}") for id in preset_ids]
        return preset_names
    return state.selected_neighborhoods
    
# --- NICEGUI SETUP ---

# Configure page layout for wide content
ui.page(title="StreetEasy Scraper", layout='wide')

# Main Header
ui.html('<h1>🏙️ StreetEasy NYC Sales Scraper</h1>').classes('text-2xl font-bold')
ui.markdown("Search for properties in Brooklyn and Manhattan powered by ScrapingBee")

# API Metrics Row (Refreshable)
api_metrics_row()

# Main Content and Sidebar
with ui.row().classes('w-full'):

    # Left Drawer (Sidebar)
    with ui.left_drawer(value=True).classes('bg-gray-100 p-4 w-1/4 min-w-80'):
        
        # STOP button (NiceGUI doesn't need st.stop, but we can stop the server)
        # ui.button('STOP', on_click=ui.stop).classes('w-full mb-4') 
        # Using a more standard NiceGUI approach:
        ui.label("Search Filters").classes('text-lg font-bold mb-4')

        # API Key Input
        ui.input(
            label="ScrapingBee API Key (Required)",
            password=True,
            on_change=lambda e: setattr(state, 'scrapingbee_api_key', e.value)
        ).classes('w-full').bind_value(state, 'scrapingbee_api_key')
        
        with ui.column().classes('w-full'):
            ui.warning("⚠️ You need a ScrapingBee API key").classes('mb-1')
            ui.link("[Get Free API Key (1,000 credits) →]", 'https://www.scrapingbee.com/', new_tab=True).classes('text-sm')
            ui.html("""
                <div class="text-xs text-gray-600 mt-2 p-2 border border-gray-300 rounded bg-white">
                    <strong>💡 Credit Usage:</strong><br>
                    - Standard request: 1 credit<br>
                    - JS rendering: 5 credits<br>
                    - Premium proxy: 10 credits
                </div>
            """).classes('w-full')
        
        ui.separator().classes('my-4')
        
        # Borough Select
        ui.select(["Brooklyn", "Manhattan"], 
            value=state.borough, 
            label="Borough", 
            on_change=lambda e: setattr(state, 'borough', e.value)
        ).classes('w-full')
        
        # Preset Checkbox
        ui.checkbox("Use My Preset Neighborhoods", 
            value=state.use_preset, 
            on_change=lambda e: setattr(state, 'use_preset', e.value)
        ).classes('mt-2')

        @ui.refreshable
        def neighborhood_select():
            """Refreshes based on the preset checkbox state."""
            if state.use_preset:
                # Mock preset info display
                preset_names = get_selected_neighborhoods()
                ui.info(f"Using preset: {', '.join(preset_names)}")
            else:
                neighborhoods_list = NEIGHBORHOODS # Assuming NEIGHBORHOODS is the same for both boroughs for simplicity
                ui.select(
                    neighborhoods_list,
                    value=state.selected_neighborhoods,
                    label="Neighborhoods (leave empty for all)",
                    multiple=True,
                    on_change=lambda e: setattr(state, 'selected_neighborhoods', e.value)
                ).classes('w-full').props('use-chips') # NiceGUI uses use-chips for multiselect tags
        
        neighborhood_select()
        
        # Other Filters
        ui.select(list(PROPERTY_TYPES.keys()), 
            value=state.property_type, 
            label="Property Type", 
            on_change=lambda e: setattr(state, 'property_type', e.value)
        ).classes('w-full mt-4')
        
        ui.number(
            label="Max Price ($, 0 for no limit)", 
            value=state.max_price, 
            min=0, step=100000, format='%.0f',
            on_change=lambda e: setattr(state, 'max_price', int(e.value))
        ).classes('w-full')
        
        ui.number(
            label="Min Square Feet (0 for no limit)", 
            value=state.min_sqft, 
            min=0, step=50, format='%.0f',
            on_change=lambda e: setattr(state, 'min_sqft', int(e.value))
        ).classes('w-full')
        
        ui.number(
            label="Max Monthly Taxes ($, 0 for no limit)", 
            value=state.max_taxes, 
            min=0, step=100, format='%.0f',
            on_change=lambda e: setattr(state, 'max_taxes', int(e.value))
        ).classes('w-full')
        
        ui.number(
            label="Max Monthly Common Charges ($, 0 for no limit)", 
            value=state.max_fees, 
            min=0, step=100, format='%.0f',
            on_change=lambda e: setattr(state, 'max_fees', int(e.value))
        ).classes('w-full')
        
        ui.number(
            label="Max Pages to Scrape", 
            value=state.max_pages, 
            min=1, max=20, step=1, format='%.0f',
            on_change=lambda e: setattr(state, 'max_pages', int(e.value))
        ).classes('w-full mt-4').tooltip("Each page has ~20-30 listings. Each page costs 1 credit.")
        
        ui.checkbox(
            "Fetch detailed info for all listings", 
            value=state.scrape_details, 
            on_change=lambda e: setattr(state, 'scrape_details', e.value)
        ).classes('mt-2').tooltip("Scrapes individual listing pages for complete data (1 credit per listing)")
        
        # Search Button (Primary action)
        ui.button("🔍 Search Listings", on_click=search_listings).props('color=primary').classes('w-full mt-6')

    # Main Content Area
    with ui.column().classes('flex-grow p-4'):
        
        # Results display (refreshable)
        results_display()
        
        # Dynamic Search URL Link
        @ui.refreshable
        def search_url_link():
            if state.search_url:
                ui.markdown(f"**URL:** [Click to View on StreetEasy]({state.search_url})").classes('mt-4')
        
        search_url_link.refresh()
        
        ui.caption("Powered by ScrapingBee API")

# --- Vercel Deployment Changes ---
# 1. Remove ui.run()
# 2. Export the FastAPI app instance for Vercel's Python runtime
# 3. Add app.on_startup() to ensure the NiceGUI setup runs

# Expose the NiceGUI app's startup method and FastAPI instance for Vercel
@app.on_startup()
def setup_nicegui():
    # This function is now called by Vercel's runtime environment
    # when the Lambda function initializes.
    pass

# The variable 'app' is the FastAPI application instance wrapped by NiceGUI
# We rename it to 'api' (a common Vercel convention) and export it.
api = app.fastapi
# --- END Vercel Deployment Changes ---