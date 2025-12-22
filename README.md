# Notion Reading Heatmap Generator

Generates a GitHub-contribution-style heatmap of your reading habits from a Notion database and saves it as an image.

Example like this:
![image](https://raw.githubusercontent.com/broodfish/Daily-Heatmap/refs/heads/main/public/heatmap.png)

## Setup

1.  **Notion Setup**:
    *   Create a Notion Integration at [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations).
    *   Get the `Internal Integration Secret` (Token).
    *   Share your Database with this integration (Three dots > Connect to > Select your integration).
    *   Get the `Datasource ID` from your database.

2.  **Database Structure**:
    *   Ensure your database has:
        *   A **Date** property.
        *   A **Rollup** property for duration.

3.  **GitHub Secrets**:
    *   Add the following secrets to your repository:
        *   `NOTION_TOKEN`: Your integration secret.
        *   `NOTION_DATASOURCE_ID`: Your database ID.
        *   `NOTION_DURATION_PROP`: Your date column name.
        *   `NOTION_TIME_PROP`: Your time column name.

## Local Development

```bash
pip install -r requirements.txt
# Set environment variables in your terminal or .env
python src/generate_heatmap.py
```

## Output

The script generates `public/heatmap.png` and `public/heatmap.html`.
