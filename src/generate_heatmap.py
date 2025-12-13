import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import pandas as pd

import matplotlib.pyplot as plt
from notion_client import Client
from dotenv import load_dotenv

def main():
    # Load environment variables from .env file if present
    # Force UTF-8 encoding to handle Chinese characters correctly
    load_dotenv(encoding='utf-8')

    # 1. Configuration
    NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
    NOTION_DATASOURCE_ID = os.environ.get("NOTION_DATASOURCE_ID")
    
    # Optional overlays for property names
    DATE_PROP = os.environ.get("NOTION_DATE_PROP")
    DURATION_PROP = os.environ.get("NOTION_DURATION_PROP")
    
    print("--- Configuration Debug ---")
    print(f"DATE_PROP: {repr(DATE_PROP)}")
    print(f"DURATION_PROP: {repr(DURATION_PROP)}")
    
    if not DATE_PROP or not DURATION_PROP:
        print("Error: NOTION_DATE_PROP or NOTION_DURATION_PROP not properly set in environment variables.")
        sys.exit(1)
    
    if not NOTION_TOKEN or not NOTION_DATASOURCE_ID:
        print("Error: NOTION_TOKEN or NOTION_DATASOURCE_ID not properly set in environment variables.")
        sys.exit(1)

    # 2. Fetch Data from Notion
    notion = Client(auth=NOTION_TOKEN)
    records = []
    
    print(f"Querying Notion Database: {NOTION_DATASOURCE_ID}...")
    
    has_more = True
    start_cursor = None
    
    while has_more:
        try:
            # Query the Data Source
            response = notion.data_sources.query(
                data_source_id=NOTION_DATASOURCE_ID,
                start_cursor=start_cursor,
                page_size=100
            )
        except Exception as e:
            print(f"Error querying Notion: {e}")
            sys.exit(1)
            
        results = response.get("results", [])
        if results and len(records) == 0:
             # DEBUG: Print the first page's properties to help debug
             # first_page_props = results[0].get("properties", {})
             # print("\n--- DEBUG: Properties Keys found in first page ---")
             # print(list(first_page_props.keys()))
             # print(f"\n--- DEBUG: Content of property '{DATE_PROP}' ---")
             # print(first_page_props.get(DATE_PROP))
             # print(f"\n--- DEBUG: Content of property '{DURATION_PROP}' ---")
             # print(first_page_props.get(DURATION_PROP))
             # print("------------------------------------------------\n")
             pass

        for page in results:
            props = page.get("properties", {})
            
            # Extract Date from Title Property (Title -> Mention -> Date)
            # User specified: DATE_PROP.title[0].mention.date.start
            try:
                # Note: DATE_PROP name might default to "Date", but user schema implies it's the Title property?
                # Usually Title property is named "Name" or "Title", but we use DATE_PROP variable.
                # If DATE_PROP is "Name", this works.
                date_prop = props.get(DATE_PROP, {})
                title_list = date_prop.get("title", [])
                if not title_list:
                    continue
                    
                date_data = title_list[0].get("mention", {}).get("date", {})
                date_str = date_data.get("start")
            except (IndexError, AttributeError):
                continue
            
            # Extract Duration from Rollup Property
            # User specified: DURATION_PROP.rollup.number
            duration_num = props.get(DURATION_PROP, {}).get("rollup", {}).get("number")
            
            if date_str and duration_num is not None:
                records.append({
                    "date": date_str,
                    "value": float(duration_num)
                })
        
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")
        print(f"Fetched {len(results)} pages. Total records so far: {len(records)}")

    if not records:
        print("No records found. Exiting.")
        # Proceed to generate an empty/dummy plot or just exit? 
        # Better to exit to avoid overwriting with blank image if something is wrong,
        # but for a daily run, maybe we want to show empty?
        # Let's generate a clear message but maybe not fail the build.
        sys.exit(0)

    # 3. Process Data
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    # Aggregate by day (summing duration if multiple entries exist per day)
    daily_data = df['value'].groupby(df.index).sum()

    # 4. Generate Heatmap (Custom Implementation)
    # Ensure public directory exists
    output_dir = Path("public")
    output_dir.mkdir(exist_ok=True)
    
    print("Generating heatmap (Custom Styling)...")
    
    # Configuration
    YEAR = datetime.now().year
    TODAY = datetime.now().date()
    
    # Generate full date range for the current year up to today
    start_date = datetime(YEAR, 1, 1).date()
    end_date = TODAY
    
    # Create complete index
    idx = pd.date_range(start_date, end_date)
    
    # Reindex data to ensure every day has a value (fill 0)
    # Ensure index is date type for matching
    df.index = df.index.date
    daily_data = daily_data.reindex(idx, fill_value=0)
    
    # Prepare Plot Data
    # We need to map each date to (Week, Day) coordinates
    # Day: Monday=0, Sunday=6 (Y-axis, usually Sunday at top 0 or bottom? GitHub has Mon(0) at top?)
    # GitHub: Mon(0) -> Sun(6). Let's put Mon at top (y=6) or bottom (y=0)? 
    # Usually standard heatmap: Mon at top.
    # We will use: Y = 6 - weekday (so Mon=6, Sun=0) or just standard grid text.
    # Let's use standard matrix coordinate: y=weekday (0=Mon, 6=Sun). invert axis later.
    
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    import numpy as np

    # Set font - Prioritize Microsoft JhengHei for Windows to avoid Arial missing glyphs
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False 

    # Custom Colors
    # 0: Gray, 1-4: Browns
    COLORS = ['#ebedf0', '#f4d6b6', '#d9a773', '#bf7e44', '#8c5931']
    def get_color(value):
        if value == 0: return COLORS[0]
        if value < 60: return COLORS[1]
        if value < 180: return COLORS[2]
        if value < 360: return COLORS[3]
        return COLORS[4]

    # Calculate dimensions
    # Weeks calculation might be tricky because of partial weeks at start
    # Simple approach: relative to start_date
    
    def get_week_num(date_obj):
        # Isocalendar week might be different year.
        # Simple relative week:
        delta = (date_obj - start_date).days
        # Adjust for start_date weekday
        start_weekday = start_date.weekday() # Mon=0, Sun=6
        return (delta + start_weekday) // 7

    total_weeks = get_week_num(end_date) + 1
    
    # Figure Size: ~16px per box?
    # Aspect ratio ~ (Weeks * size) : (7 * size)
    # figsize is in inches. 
    fig_width = 16
    fig_height = 3 # Compact height
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    ax = fig.add_axes([0, 0, 1, 1]) # Full span

    # Draw Boxes
    BOX_SIZE = 0.8 # leave gap
    GAP = (1 - BOX_SIZE) / 2
    
    for date_val, value in daily_data.items():
        date_obj = date_val.date() if isinstance(date_val, datetime) else date_val
        
        week_idx = get_week_num(date_obj)
        day_idx = date_obj.weekday() # 0=Mon, 6=Sun
        
        # Invert Y so Mon is at Top (Index 0 in grid, but usually plotted upwards?)
        # Let's plot typical coords: Y goes up.
        # We want Mon at Top. So Mon: y=6, Sun: y=0
        y_pos = 6 - day_idx
        x_pos = week_idx
        
        color = get_color(value)
        
        # Rounded Rectangle
        rect = mpatches.FancyBboxPatch(
            (x_pos + GAP, y_pos + GAP),
            BOX_SIZE, BOX_SIZE,
            boxstyle="round,pad=-0.005,rounding_size=0.1", # Adjusted roundness
            facecolor=color,
            edgecolor=None,
            linewidth=0 # Remove border
        )
        ax.add_patch(rect)

    # Set Aspect and Limits
    ax.set_xlim(-1, total_weeks + 1)
    ax.set_ylim(-1, 7.5)
    ax.set_aspect('equal')
    ax.axis('off') # Hide axes lines/ticks

    # Add Month Labels (Top)
    # Place label at the first week of each month
    current_month = -1
    for date_val in daily_data.index:
        date_obj = date_val.date() if isinstance(date_val, datetime) else date_val
        if date_obj.month != current_month:
            # New month found
            current_month = date_obj.month
            week_idx = get_week_num(date_obj)
            # Label position: x=week, y=7.5 (above Mon)
            ax.text(week_idx, 7.5, str(current_month), 
                    ha='left', va='center', fontsize=10, color='#666')

    # Add Day Labels (Left) - REMOVED per user request (font issues in CI)
    pass

    output_path = output_dir / "heatmap.png"
    # Increase DPI for better resolution on mobile/Retina screens
    plt.savefig(output_path, bbox_inches='tight', pad_inches=0.2, transparent=True, dpi=300)
    print(f"Heatmap saved to {output_path}")

    # Generate HTML with cache-busting timestamp
    timestamp = int(datetime.now().timestamp())
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reading Heatmap</title>
    <style>
        body, html {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            background: transparent;
            overflow: hidden; /* Hide default scrollbars first */
        }}
        .container {{
            width: 100%;
            height: 100%;
            overflow-x: auto; /* Allow horizontal scrolling */
            overflow-y: hidden;
            display: flex;
            align-items: center; /* Vertically center */
            /* Hide scrollbar for cleaner look in Notion if preferred, or keep it */
            scrollbar-width: thin; 
        }}
        img {{
            /* Fill vertical height of the container (Notion block) */
            height: 90%; 
            width: auto; /* Maintain aspect ratio */
            max-width: none; /* Allow it to overflow horizontally */
            display: block;
            margin: 0 auto;
        }}
        /* Mobile optimization: make it bigger to be readable */
        @media (max-width: 480px) {{
            img {{
                height: 80%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container" id="scrollContainer">
        <img src="heatmap.png?t={timestamp}" alt="Reading Heatmap">
    </div>

    <script>
        // Auto-scroll to the farthest right (Today)
        window.onload = function() {{
            const container = document.getElementById('scrollContainer');
            container.scrollLeft = container.scrollWidth;
        }};
    </script>
</body>
</html>
    """
    
    html_path = output_dir / "heatmap.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content.strip())
    print(f"HTML wrapper saved to {html_path}")

if __name__ == "__main__":
    main()
