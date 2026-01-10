import time
import sys

import sys
import os
import django

# 1. Add Project Root to Path (Go up 3 levels from src/file.py to root)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# 2. Point to your Django Settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "unlimited_exposure.settings")

# 3. Import Settings (Django will auto-load now)
from django.conf import settings

# 4. Boot Django
if not settings.configured:
    django.setup()

#------------------

try:
    from firecrawl import Firecrawl
except ImportError:
    try:
        from firecrawl import FirecrawlApp as Firecrawl
    except ImportError:
        print("❌ Critical Error: 'firecrawl-py' not found.")
        sys.exit(1)

class WebScraper:
    def __init__(self):
        if not settings.FIRECRAWL_API_KEY:
            raise ValueError("❌ FIRECRAWL_API_KEY is missing in settings.py")
            
        self.app = Firecrawl(api_key=settings.FIRECRAWL_API_KEY)

    def scrape_page(self, url: str):
        print(f"🔥 Firecrawling site: {url} ...")
        
        try:
            # 1. SEND REQUEST
            print("   ... Request sent, waiting for Firecrawl job to complete (this might take 10-20s) ...")
            crawl_status = self.app.crawl(
                url, 
                limit=5, # Reduced limit to 5 for faster debugging
                scrape_options={'formats': ['markdown']},
                poll_interval=2
            )
            
            # 2. DEBUG PRINT RAW RESPONSE
            print("   ... Job returned! Analyzing response ...")
            # We try to print a summary of the type to debug
            print(f"   [DEBUG] Response Type: {type(crawl_status)}")
            if hasattr(crawl_status, '__dict__'):
                print(f"   [DEBUG] Attributes: {crawl_status.__dict__.keys()}")
            elif isinstance(crawl_status, dict):
                print(f"   [DEBUG] Keys: {crawl_status.keys()}")

            # 3. NORMALIZE DATA
            data_list = []
            if hasattr(crawl_status, 'data'):
                data_list = crawl_status.data
            elif isinstance(crawl_status, dict) and 'data' in crawl_status:
                data_list = crawl_status['data']
            elif isinstance(crawl_status, list):
                data_list = crawl_status

            print(f"   [DEBUG] Pages found: {len(data_list) if data_list else 0}")

            if not data_list:
                print(f"⚠️ Warning: Firecrawl returned successful status but NO data pages.")
                return ""

            combined_content = ""
            page_count = 0
            
            for item in data_list:
                # Handle Dict vs Object
                if isinstance(item, dict):
                    markdown = item.get('markdown', '')
                    metadata = item.get('metadata', {}) or {}
                    source_url = metadata.get('sourceURL', url)
                else:
                    markdown = getattr(item, 'markdown', '')
                    metadata = getattr(item, 'metadata', None)
                    source_url = getattr(metadata, 'source_url', url) if metadata else url

                # Block check
                if "Service Temporarily Unavailable" in markdown:
                    print(f"   ⚠️ SKIP: {source_url} (Blocked/Geo-fenced)")
                    continue

                if markdown:
                    combined_content += f"\n\n--- SOURCE: {source_url} ---\n{markdown}"
                    page_count += 1
            
            print(f"✅ Successfully extracted text from {page_count} pages.")
            return combined_content
            
        except Exception as e:
            print(f"❌ Failed to crawl {url}: {e}")
            import traceback
            traceback.print_exc()
            return ""

if __name__ == "__main__":
    try:
        scraper = WebScraper()
        print(scraper.scrape_page("https://docs.firecrawl.dev"))
    except Exception as e:
        print(e)