"""
Visualization functions for StreetEasy data (REVISED and CORRECTED)
Contains all Plotly Express visualizations, optimized for buyer insights.
"""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np


def prepare_data(df):
    """Prepare dataframe for visualizations - add calculated fields and ensure required columns exist"""
    df_viz = df.copy()
    
    # Calculate price per square foot
    df_viz['price_per_sqft'] = df_viz.apply(
        lambda row: row['price'] / row['sqft'] if pd.notnull(row['price']) and pd.notnull(row['sqft']) and row['sqft'] > 0 else None,
        axis=1
    )
    
    # Calculate total monthly cost
    df_viz['total_monthly_cost'] = df_viz.apply(
        lambda row: (row.get('taxes', 0) or 0) + (row.get('fees', 0) or 0),
        axis=1
    )
    
    # Ensure neighborhood column exists
    if 'neighborhood' not in df_viz.columns or df_viz['neighborhood'].isnull().all():
        df_viz['neighborhood'] = 'Unknown'
        
    # Ensure beds/baths columns exist for robust plots
    df_viz['bedrooms'] = df_viz.get('bedrooms', pd.Series(0, index=df_viz.index)).fillna(0).astype(int)
    df_viz['bathrooms'] = df_viz.get('bathrooms', pd.Series(0, index=df_viz.index)).fillna(0) # Keep float for half-baths
    
    return df_viz


def create_price_distribution(df):
    """Create histogram showing price distribution"""
    fig = px.histogram(
        df,
        x='price',
        nbins=50, 
        title='1. Price Distribution (All Listings)',
        labels={'price': 'Price ($)', 'count': 'Number of Listings'},
        color_discrete_sequence=['#1f77b4']
    )
    
    fig.update_layout(
        xaxis_tickformat='$,.0f',
        showlegend=False,
        height=400
    )
    
    return fig


def create_price_vs_sqft(df):
    """
    REVISED: Scatter plot of price vs square footage, color-coded by neighborhood.
    """
    # Filter out nulls
    df_filtered = df[(df['price'].notnull()) & (df['sqft'].notnull())].copy()
    
    if len(df_filtered) == 0:
        return None
    
    # Use 'neighborhood' for color if available
    color_var = 'neighborhood' if df_filtered['neighborhood'].nunique() > 1 else None
    
    fig = px.scatter(
        df_filtered,
        x='sqft',
        y='price',
        color=color_var,
        title='2. Price vs Square Footage (Colored by Neighborhood)',
        labels={'sqft': 'Square Feet', 'price': 'Price ($)', 'neighborhood': 'Neighborhood'},
        hover_data=['address', 'neighborhood', 'price_per_sqft'],
        trendline='ols',
        color_discrete_sequence=px.colors.qualitative.Plotly
    )
    
    fig.update_layout(
        yaxis_tickformat='$,.0f',
        xaxis_tickformat=',',
        height=550
    )
    
    return fig


def create_price_per_sqft_bar(df):
    """
    REVISED: Create bar chart of average price per sqft by neighborhood, 
    including the count of listings.
    """
    df_filtered = df[df['price_per_sqft'].notnull()].copy()
    
    if len(df_filtered) == 0:
        return None
    
    if 'neighborhood' not in df.columns or df['neighborhood'].nunique() <= 1:
        avg_price_sqft = df_filtered['price_per_sqft'].mean()
        fig = go.Figure(data=[
            go.Bar(x=['All Listings'], y=[avg_price_sqft], marker_color='#d62728',
                   customdata=[df_filtered.shape[0]], hovertemplate='Avg Price/SqFt: $%{y:,.0f}<br>Listings: %{customdata[0]:,}')
        ])
        fig.update_layout(title='3. Average Price per Square Foot', yaxis_title='$ per Sq Ft', yaxis_tickformat='$,.0f', height=400)
    else:
        # Group by neighborhood and calculate mean and count
        agg_data = df_filtered.groupby('neighborhood').agg(
            price_per_sqft=('price_per_sqft', 'mean'),
            count=('price_per_sqft', 'count')
        ).sort_values(by='price_per_sqft', ascending=False).reset_index()

        fig = px.bar(
            agg_data,
            x='neighborhood',
            y='price_per_sqft',
            title='3. Average Price per Square Foot by Neighborhood',
            labels={'neighborhood': 'Neighborhood', 'price_per_sqft': '$ per Sq Ft'},
            color='price_per_sqft',
            color_continuous_scale='Reds',
            custom_data=['count'],
        )
        
        # Add count to hover template
        fig.update_traces(hovertemplate='Neighborhood: %{x}<br>Avg Price/SqFt: $%{y:,.0f}<br>Listings: %{customdata[0]:,}<extra></extra>')

        fig.update_layout(
            yaxis_tickformat='$,.0f',
            xaxis_tickangle=-45,
            height=500
        )
    
    return fig


def create_beds_baths_vs_price(df):
    """NEW: Bar chart showing median price by Bedrooms and Bathrooms."""
    df_filtered = df[(df['price'].notnull()) & (df['bedrooms'].notnull()) & (df['bathrooms'].notnull())].copy()
    
    if len(df_filtered) < 5:
        return None

    # Grouping to calculate median price
    beds_agg = df_filtered.groupby('bedrooms')['price'].median().sort_index().reset_index()
    baths_agg = df_filtered.groupby('bathrooms')['price'].median().sort_index().reset_index()
    
    # Create subplots
    fig = make_subplots(rows=1, cols=2, 
                        subplot_titles=("Median Price by Bedrooms", "Median Price by Bathrooms"))

    # Bedroom chart
    fig.add_trace(
        go.Bar(
            x=beds_agg['bedrooms'], 
            y=beds_agg['price'], 
            name='Bedrooms', 
            marker_color='#6aa84f' # Green
        ),
        row=1, col=1
    )

    # Bathroom chart
    fig.add_trace(
        go.Bar(
            x=baths_agg['bathrooms'], 
            y=baths_agg['price'], 
            name='Bathrooms', 
            marker_color='#f9cb9c' # Orange
        ),
        row=1, col=2
    )

    fig.update_layout(
        title_text='4. Median Price Comparison by Bedrooms and Bathrooms',
        showlegend=False,
        height=450
    )
    
    fig.update_yaxes(tickformat='$,.0f', title_text='Median Price ($)')
    fig.update_xaxes(title_text='Count', tick0=0, dtick=1)
    
    return fig


def create_days_on_market_distribution(df):
    """
    NEW: Histogram/Boxplot of Days on Market (DOM) by Neighborhood. 
    A crucial indicator of market speed and negotiation power.
    """
    if 'days_on_market' not in df.columns:
        return None
        
    df_filtered = df[(df['days_on_market'].notnull()) & (df['days_on_market'] >= 0)].copy()

    if len(df_filtered) < 10:
        return None
        
    if df_filtered['neighborhood'].nunique() > 1:
        # Show boxplot comparison if multiple neighborhoods exist
        fig = px.box(
            df_filtered,
            x='neighborhood',
            y='days_on_market',
            title='5. Days on Market (DOM) by Neighborhood',
            labels={'neighborhood': 'Neighborhood', 'days_on_market': 'Days on Market'},
            color='neighborhood',
        )
        fig.update_layout(
            xaxis_tickangle=-45,
            showlegend=False,
            height=500
        )
    else:
        # Show a simple histogram if only one neighborhood
        fig = px.histogram(
            df_filtered,
            x='days_on_market',
            title='5. Days on Market (DOM) Distribution',
            labels={'days_on_market': 'Days on Market', 'count': 'Number of Listings'},
            nbins=30,
            color_discrete_sequence=['#8c564b']
        )
        fig.update_layout(showlegend=False, height=400)

    return fig


def create_total_cost_vs_price(df):
    """
    REVISED: Scatter plot of purchase price vs monthly carrying costs, 
    colored by Price per SqFt to link value and cost.
    """
    df_filtered = df[(df['price'].notnull()) & (df['total_monthly_cost'] > 0) & (df['price_per_sqft'].notnull())].copy()
    
    if len(df_filtered) == 0:
        return None
    
    fig = px.scatter(
        df_filtered,
        x='price',
        y='total_monthly_cost',
        title='6. Purchase Price vs Monthly Costs (Colored by Price/SqFt)',
        labels={'price': 'Purchase Price ($)', 'total_monthly_cost': 'Monthly Costs ($)', 
                'price_per_sqft': 'Price/SqFt ($)'},
        hover_data=['address', 'taxes', 'fees', 'price_per_sqft'],
        color='price_per_sqft', 
        color_continuous_scale='plasma'
    )
    
    fig.update_layout(
        xaxis_tickformat='$,.0f',
        yaxis_tickformat='$,.0f',
        height=500
    )
    
    return fig


def create_monthly_costs_breakdown(df):
    """
    CORRECTED: Create stacked bar chart of monthly costs (taxes + fees).
    Fixed the `fillna` error by applying it only to numeric columns.
    """
    df_filtered = df[(df['taxes'].notnull()) | (df['fees'].notnull())].copy()
    
    if len(df_filtered) == 0:
        return None
    
    # Fill nulls with 0 for visualization (before aggregation)
    df_filtered['taxes'] = df_filtered['taxes'].fillna(0)
    df_filtered['fees'] = df_filtered['fees'].fillna(0)
    
    # --- Bins and Labels ---
    cost_bins = [0, 1000, 2000, 3000, 5000, 10000, np.inf]
    cost_labels = ['<$1k', '$1-2k', '$2-3k', '$3-5k', '$5-10k', '>$10k']
    
    df_filtered['cost_category'] = pd.cut(
        df_filtered['total_monthly_cost'],
        bins=cost_bins, 
        labels=cost_labels,
        right=True,
        include_lowest=True,
    )
    
    cost_summary = df_filtered.groupby('cost_category', observed=False).agg(
        taxes=('taxes', 'mean'),
        fees=('fees', 'mean')
    ).reset_index()

    # --- FIX: Only fill NaN in the numeric aggregate columns ---
    # This prevents the TypeError when trying to fill the categorical column with an integer 0.
    cost_summary[['taxes', 'fees']] = cost_summary[['taxes', 'fees']].fillna(0)
    # -----------------------------------------------------------
    
    fig = go.Figure(data=[
        go.Bar(name='Monthly Taxes (Avg)', x=cost_summary['cost_category'], y=cost_summary['taxes'], marker_color='#9467bd'),
        go.Bar(name='Monthly Fees (Avg)', x=cost_summary['cost_category'], y=cost_summary['fees'], marker_color='#8c564b')
    ])
    
    fig.update_layout(
        barmode='stack',
        title='7. Average Monthly Costs Breakdown by Total Cost Range',
        xaxis_title='Total Monthly Cost Range',
        yaxis_title='Average Amount ($)',
        yaxis_tickformat='$,.0f',
        height=400
    )
    
    return fig


def create_neighborhood_comparison(df):
    """Box plot comparing price distribution by neighborhoods"""
    if 'neighborhood' not in df.columns or df['neighborhood'].nunique() <= 1:
        return None
    
    df_filtered = df[df['price'].notnull()].copy()
    
    if len(df_filtered) == 0:
        return None
    
    fig = px.box(
        df_filtered,
        x='neighborhood',
        y='price',
        title='8. Price Distribution Comparison by Neighborhood',
        labels={'neighborhood': 'Neighborhood', 'price': 'Price ($)'},
        color='neighborhood'
    )
    
    fig.update_layout(
        yaxis_tickformat='$,.0f',
        xaxis_tickangle=-45,
        showlegend=False,
        height=500
    )
    
    return fig


def create_affordability_heatmap(df):
    """Create heatmap showing inventory by neighborhood and price range"""
    if 'neighborhood' not in df.columns or df['neighborhood'].nunique() <= 1:
        return None
    
    df_filtered = df[df['price'].notnull()].copy()
    
    if len(df_filtered) == 0:
        return None
    
    # Create price bins
    price_bins = [0, 500000, 750000, 1000000, 1500000, 2500000, 5000000, np.inf] 
    price_labels = ['<$500k', '$500-750k', '$750k-1M', '$1-1.5M', '$1.5-2.5M', '$2.5-5M', '>$5M']
    
    df_filtered['price_range'] = pd.cut(
        df_filtered['price'],
        bins=price_bins,
        labels=price_labels,
        right=False, 
        include_lowest=True
    )
    
    # Count listings by neighborhood and price range
    heatmap_data = df_filtered.groupby(['neighborhood', 'price_range'], observed=False).size().unstack(fill_value=0)
    
    fig = px.imshow(
        heatmap_data,
        title='9. Inventory Heatmap: Neighborhoods vs Price Ranges',
        labels=dict(x='Price Range', y='Neighborhood', color='Number of Listings'),
        color_continuous_scale='YlOrRd',
        aspect='auto',
        text_auto=True 
    )
    
    fig.update_layout(
        xaxis_tickangle=-45,
        height=550
    )
    
    return fig


def create_all_visualizations(df):
    """Create all visualizations and return them as a dictionary"""
    df_viz = prepare_data(df)
    
    visualizations = {
        'price_distribution': create_price_distribution(df_viz),
        'price_vs_sqft': create_price_vs_sqft(df_viz),
        'price_per_sqft': create_price_per_sqft_bar(df_viz),
        'beds_baths_vs_price': create_beds_baths_vs_price(df_viz),
        'days_on_market_distribution': create_days_on_market_distribution(df_viz),
        'total_cost_vs_price': create_total_cost_vs_price(df_viz),
        'monthly_costs': create_monthly_costs_breakdown(df_viz),
        'neighborhood_comparison': create_neighborhood_comparison(df_viz),
        'affordability_heatmap': create_affordability_heatmap(df_viz)
    }
    
    # Filter out None values (visualizations that couldn't be created due to missing data)
    visualizations = {k: v for k, v in visualizations.items() if v is not None}
    
    return visualizations
