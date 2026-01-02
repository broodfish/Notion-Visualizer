import os
import sys
import collections
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from notion_client import Client
from wordcloud import WordCloud
import matplotlib.font_manager as fm

def get_chinese_font_path():
    """Attempt to find a suitable Chinese font on the system."""
    # List of common Chinese font names on macOS/Linux/Windows
    # Prioritize macOS fonts since user is on macOS
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "simhei.ttf",
        "msyh.ttc",
        "Arial Unicode MS"
    ]
    
    for path in candidates:
        if os.path.exists(path):
            return path
            
    # Fallback: try to find via font_manager
    # macOS 'PingFang TC' or 'Heiti TC'
    try:
        font_path = fm.findfont(fm.FontProperties(family=['Heiti TC', 'PingFang TC', 'Microsoft JhengHei']))
        if font_path:
            return font_path
    except:
        pass

    return None

def main():
    # Load environment variables
    load_dotenv(encoding='utf-8')

    # Configuration
    NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
    NOTION_DATASOURCE_ID = os.environ.get("NOTION_YEAR_DATASOURCE_ID")
    TAGS_PROP = os.environ.get("TAGS_PROP", "Tags") # Default to "Tags" if not set

    if not NOTION_TOKEN or not NOTION_DATASOURCE_ID:
        print("Error: NOTION_TOKEN or NOTION_YEAR_DATASOURCE_ID not set.")
        sys.exit(1)
    
    if not TAGS_PROP:
         print("Error: TAGS_PROP is empty.")
         sys.exit(1)

    print(f"Configuration:")
    print(f"  Datasource ID: {NOTION_DATASOURCE_ID}")
    print(f"  Tags Property: {TAGS_PROP}")

    # Initialize Notion Client
    notion = Client(auth=NOTION_TOKEN)
    
    tag_list = []
    
    print("Querying Notion...")
    has_more = True
    start_cursor = None
    
    while has_more:
        try:
            response = notion.data_sources.query(
                data_source_id=NOTION_DATASOURCE_ID,
                start_cursor=start_cursor,
                page_size=100
            )
        except Exception as e:
            print(f"Error querying Notion: {e}")
            sys.exit(1)
        
        results = response.get("results", [])
        
        for page in results:
            props = page.get("properties", {})
            tag_prop = props.get(TAGS_PROP)
            
            if not tag_prop:
                continue
                
            prop_type = tag_prop.get("type")
            
            names = []
            if prop_type == "multi_select":
                names = [options["name"] for options in tag_prop.get("multi_select", [])]
            elif prop_type == "select":
                select_obj = tag_prop.get("select")
                if select_obj:
                    names = [select_obj.get("name")]
            elif prop_type == "rich_text":
                # Fallback if tags are comma separated text
                rt = tag_prop.get("rich_text", [])
                if rt:
                    text_content = "".join([t.get("plain_text", "") for t in rt])
                    # Split by common separators
                    names = [x.strip() for x in text_content.replace("，", ",").split(",") if x.strip()]
            elif prop_type == "formula":
                 # Handle Formula returning a string of tags
                 formula_val = tag_prop.get("formula", {})
                 # Formula can return string, number, boolean, date. Assuming string here based on debug.
                 if formula_val.get("type") == "string":
                     text_content = formula_val.get("string") or ""
                     names = [x.strip() for x in text_content.replace("，", ",").split(",") if x.strip()]
            
            tag_list.extend(names)
            
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")
        print(f"Fetched {len(results)} pages. Total tags accumulated: {len(tag_list)}")

    if not tag_list:
        print("No tags found.")
        sys.exit(0)

    # Count Frequencies
    text_freq = collections.Counter(tag_list)
    print(f"Top tags: {text_freq.most_common(10)}")

    # --- Font Setup ---
    # User provided font (ExtraBold)
    font_name = "ChironGoRoundTC-ExtraBold.ttf"
    local_font_path = Path(font_name)
    
    # Check if exists
    if not local_font_path.exists():
        print(f"Font {font_name} not found in root directory.")
        print(f"Please ensure it is placed in: {os.getcwd()}")
        print("Falling back to system font for now...")
        local_font_path = Path(get_chinese_font_path())

    final_font_path = str(local_font_path) if local_font_path.exists() else get_chinese_font_path()
    print(f"Using font: {final_font_path}")
    
    # --- Custom Colors ---
    import random
    def similar_color_func(word, font_size, position, orientation, random_state=None, **kwargs):
        # Aesthetic palette: Earthy/Wenqing tones
        # Muted variations of Brown, Teal, Slate, Sage
        colors = [
            "hsl(30, 40%, 50%)",   # Muted Brown
            "hsl(180, 20%, 40%)",  # Dark Teal
            "hsl(210, 30%, 60%)",  # Muted Blue/Slate
            "hsl(150, 20%, 50%)",  # Sage Green
            "hsl(350, 30%, 60%)",  # Dusty Rose
            "hsl(25, 60%, 45%)",   # Burnt Orange
            "hsl(200, 40%, 45%)"   # Steel Blue
        ]
        return random.choice(colors)

    # --- Generate ---
    # Create public directory
    output_dir = Path("public")
    output_dir.mkdir(exist_ok=True)
    
    wc = WordCloud(
        font_path=final_font_path,
        width=1200, # Increased resolution
        height=600,
        mode="RGBA",
        background_color=None, # Transparent
        min_font_size=12,
        max_font_size=120,
        margin=5,
        prefer_horizontal=1.0, # NO ROTATION
        color_func=similar_color_func, # Custom colors
        regexp=r"\w+" # Simple regex
    )
    
    wc.generate_from_frequencies(text_freq)
    
    # Save Image
    output_img_path = output_dir / "word_cloud.png"
    wc.to_file(str(output_img_path))
    print(f"Saved word cloud image to {output_img_path}")
    
    # Generate HTML wrapper
    timestamp = int(datetime.now().timestamp())
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reading Tags Word Cloud</title>
    <style>
        body, html {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            background: transparent;
        }}
        img {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }}
    </style>
</head>
<body>
    <img src="word_cloud.png?t={timestamp}" alt="Word Cloud">
</body>
</html>
    """
    
    output_html_path = output_dir / "word_cloud.html"
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content.strip())
        
    print(f"Saved HTML wrapper to {output_html_path}")

if __name__ == "__main__":
    main()
