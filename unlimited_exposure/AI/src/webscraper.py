import time
import sys

try:
    # Latest SDK uses 'Firecrawl' class
    from firecrawl import Firecrawl
except ImportError:
    try:
        from firecrawl import FirecrawlApp as Firecrawl
    except ImportError:
        print("❌ Critical Error: 'firecrawl-py' not found. Please run: pip install firecrawl-py")
        sys.exit(1)

from config import settings

class WebScraper:
    def __init__(self):
        if not settings.FIRECRAWL_API_KEY:
            raise ValueError("❌ FIRECRAWL_API_KEY is missing in .env or config.py")
            
        self.app = Firecrawl(api_key=settings.FIRECRAWL_API_KEY)

    def scrape_page(self, url: str):
        """
        Uses Firecrawl to crawl the website and extract markdown.
        Robustly handles different SDK response formats (Dict vs Object).
        """
        print(f"🔥 Firecrawling site: {url} ...")
        
        try:
            # Parameters for the crawl
            # Note: You can try adding 'country': 'IN' to scrapeOptions if using a proxy plan,
            # but standard requests might still be blocked by NSE.
            crawl_status = self.app.crawl(
                url, 
                limit=10, # Keep limit low for testing
                scrape_options={'formats': ['markdown']},
                poll_interval=2
            )
            
            # --- ROBUST RESPONSE PARSING ---
            data_list = []

            # Case A: Response is an Object with a .data attribute (New SDK)
            if hasattr(crawl_status, 'data'):
                data_list = crawl_status.data
            
            # Case B: Response is a Dictionary with a 'data' key (Old SDK/API)
            elif isinstance(crawl_status, dict) and 'data' in crawl_status:
                data_list = crawl_status['data']
            
            # Case C: Response is directly a List (Edge case)
            elif isinstance(crawl_status, list):
                data_list = crawl_status

            if not data_list:
                print(f"⚠️ Warning: No content returned for {url}")
                print(f"Debug Info: {crawl_status}")
                return ""

            combined_content = ""
            page_count = 0
            
            for item in data_list:
                # Extract fields dynamically (Handle Object vs Dict)
                if isinstance(item, dict):
                    # It's a dictionary
                    markdown = item.get('markdown', '')
                    metadata = item.get('metadata', {})
                    # Handle metadata being None or Dict
                    if metadata is None: metadata = {}
                    source_url = metadata.get('sourceURL', url)
                else:
                    # It's likely a Pydantic object (Document)
                    markdown = getattr(item, 'markdown', '')
                    metadata = getattr(item, 'metadata', None)
                    # Try to get source_url from metadata object or use default
                    source_url = url
                    if metadata and hasattr(metadata, 'source_url'):
                        source_url = metadata.source_url
                    elif metadata and hasattr(metadata, 'url'):
                        source_url = metadata.url

                # Check for "Service Unavailable" or blocking messages
                if "Service Temporarily Unavailable" in markdown:
                    print(f"⚠️ SKIP: {source_url} (Blocked/Geo-fenced)")
                    continue

                if markdown:
                    combined_content += f"\n\n--- SOURCE: {source_url} ---\n{markdown}"
                    page_count += 1
            
            if page_count == 0:
                print("⚠️ Scrape finished but all pages were empty or blocked.")
                return ""

            print(f"✅ Successfully crawled {page_count} pages.")
            return combined_content
            
        except AttributeError as e:
            print(f"❌ SDK Error: {e}")
            return ""
        except Exception as e:
            print(f"❌ Failed to crawl {url}: {e}")
            return ""

if __name__ == "__main__":
    try:
        scraper = WebScraper()
        print(scraper.scrape_page("https://docs.firecrawl.dev"))
    except Exception as e:
        print(e)