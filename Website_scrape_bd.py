import urllib.request
import urllib.parse
import urllib.error
import http.client
import json
import ssl
import webbrowser
import time
import sys
import os
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from datetime import datetime

class AdvancedDarkBossScraper(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.users = []
        self.current_data = {}
        self.in_user_card = False
        self.current_tag = None
        self.current_classes = []
        
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        attrs_dict = dict(attrs)
        self.current_classes = attrs_dict.get('class', '').split() if 'class' in attrs_dict else []
        
        # Multiple methods to detect user profile elements
        user_indicators = [
            # Class-based detection
            any(cls in ['user', 'profile', 'member', 'user-card', 'user_info', 
                       'profile-card', 'user-profile', 'user-item', 'user-block',
                       'user-details', 'author', 'user-name', 'user-avatar'] for cls in self.current_classes),
            
            # ID-based detection
            'id' in attrs_dict and any(x in attrs_dict['id'] for x in ['user', 'profile', 'member']),
            
            # Data attribute detection
            any(attr[0].startswith('data-user') for attr in attrs if isinstance(attr, tuple)),
        ]
        
        if any(user_indicators):
            self.in_user_card = True
            self.current_data = {}
        
        # Extract user information from links
        if tag == 'a' and 'href' in attrs_dict:
            href = attrs_dict['href']
            if any(x in href for x in ['/user/', '/profile/', '/member/', '/users/', '/author/']):
                self.current_data['profile_url'] = urljoin(self.base_url, href)
                if 'name' not in self.current_data:
                    # Try to extract name from link text or URL
                    if href.split('/')[-1].replace('-', ' ').replace('_', ' ').strip():
                        self.current_data['name'] = href.split('/')[-1].replace('-', ' ').replace('_', ' ').title()
        
        # Extract avatar from images
        if tag == 'img' and 'src' in attrs_dict and self.in_user_card:
            src = attrs_dict['src']
            if any(x in src for x in ['avatar', 'profile', 'user', 'gravatar']):
                self.current_data['avatar'] = urljoin(self.base_url, src)
            elif 'alt' in attrs_dict and any(x in attrs_dict['alt'].lower() for x in ['user', 'profile', 'avatar']):
                self.current_data['avatar'] = urljoin(self.base_url, src)
    
    def handle_data(self, data):
        if self.in_user_card and data.strip():
            data = data.strip()
            if len(data) > 2:  # Ignore very short text
                # Name detection with various patterns
                if 'name' not in self.current_data and not any(c in data for c in ['@', '://', 'http']) and len(data) < 50:
                    if (re.match(r'^[A-Za-z\s\.]+$', data) or 
                        (len(data.split()) >= 1 and len(data.split()) <= 3)):
                        self.current_data['name'] = data
                
                # Email detection
                elif 'email' not in self.current_data and re.match(r'[^@]+@[^@]+\.[^@]+', data):
                    self.current_data['email'] = data
                
                # Username detection
                elif 'username' not in self.current_data and re.match(r'^[a-zA-Z0-9_\.\-]+$', data) and 3 <= len(data) <= 20:
                    self.current_data['username'] = data
                
                # Bio or description detection
                elif 'bio' not in self.current_data and len(data) > 10 and len(data) < 150:
                    self.current_data['bio'] = data
    
    def handle_endtag(self, tag):
        if tag in ['div', 'section', 'article', 'li', 'tr', 'ul', 'ol'] and self.in_user_card:
            if self.current_data and len(self.current_data) > 1:  # At least 2 pieces of info
                # Add some default values if missing
                if 'name' not in self.current_data and 'username' in self.current_data:
                    self.current_data['name'] = self.current_data['username']
                
                self.users.append(self.current_data)
            self.in_user_card = False
            self.current_data = {}

def get_web_content(url):
    """Download content from URL with better error handling"""
    try:
        # Bypass SSL verification (for educational purposes)
        context = ssl._create_unverified_context()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=context, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[!] Page not found (404): {url}")
        else:
            print(f"[!] HTTP Error {e.code}: {url}")
        return None
    except urllib.error.URLError as e:
        print(f"[!] URL Error: {e.reason} - {url}")
        return None
    except Exception as e:
        print(f"[!] Error accessing {url}: {e}")
        return None

def extract_users_from_patterns(content, base_url):
    """Extract users using regex patterns as fallback"""
    users = []
    
    # Try to find user profiles using various patterns
    patterns = [
        # Social media profiles
        r'https?://(?:www\.)?(facebook|twitter|instagram|linkedin)\.com/[a-zA-Z0-9_\-\.]+',
        
        # Email patterns
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        
        # Name patterns in HTML
        r'class="[^"]*(name|user-name|profile-name|author-name)[^"]*"[^>]*>([^<]+)<',
        
        # Username patterns
        r'class="[^"]*(username|user-login|profile-username)[^"]*"[^>]*>([^<]+)<',
    ]
    
    for pattern in patterns:
        try:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[1] if len(match) > 1 else match[0]
                
                user_data = {}
                if '@' in match and '.' in match:
                    user_data['email'] = match
                    user_data['name'] = match.split('@')[0]
                elif any(domain in match for domain in ['facebook', 'twitter', 'instagram', 'linkedin']):
                    user_data['social'] = match
                    user_data['name'] = match.split('/')[-1].replace('-', ' ').title()
                else:
                    user_data['name'] = match.strip()
                
                if user_data:
                    users.append(user_data)
        except Exception as e:
            print(f"[!] Error with pattern {pattern}: {e}")
            continue
    
    return users

def scrape_users_from_website(url):
    """Extract user information from website using multiple methods"""
    print(f"[*] Collecting data from {url}...")
    
    content = get_web_content(url)
    if not content:
        print("[!] Failed to load website")
        return []
    
    # Method 1: HTML parsing
    print("[*] Method 1: Parsing HTML structure...")
    parser = AdvancedDarkBossScraper(url)
    parser.feed(content)
    users = parser.users
    
    # Method 2: Regex patterns (fallback)
    if not users:
        print("[*] Method 2: Trying regex patterns...")
        users = extract_users_from_patterns(content, url)
    
    # Method 3: Try common endpoints (only if we have a valid base domain)
    if not users:
        print("[*] Method 3: Trying common user endpoints...")
        users = try_common_endpoints(url)
    
    return users

def try_common_endpoints(base_url):
    """Try to access common user profile endpoints with better error handling"""
    users = []
    common_endpoints = [
        '/users', '/profiles', '/members', '/community', '/authors',
        '/wp-json/wp/v2/users', '/api/users', '/user/list', '/users/list',
        '/profiles/list', '/members/list', '/community/users'
    ]
    
    parsed_url = urlparse(base_url)
    base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    for endpoint in common_endpoints:
        try:
            user_url = urljoin(base_domain, endpoint)
            print(f"[*] Trying endpoint: {user_url}")
            
            content = get_web_content(user_url)
            if content:
                # Try to parse as JSON first
                if any(api in endpoint for api in ['wp-json', '/api/']):
                    try:
                        data = json.loads(content)
                        if isinstance(data, list):
                            for item in data:
                                if 'name' in item or 'username' in item:
                                    users.append(item)
                            if users:
                                print(f"[+] Found {len(users)} users in API endpoint")
                                break
                    except json.JSONDecodeError:
                        # Not JSON, continue with HTML parsing
                        pass
                
                # Try HTML parsing
                parser = AdvancedDarkBossScraper(user_url)
                parser.feed(content)
                if parser.users:
                    users.extend(parser.users)
                    print(f"[+] Found {len(parser.users)} users in {endpoint}")
                    break
        except Exception as e:
            print(f"[!] Error accessing {endpoint}: {e}")
            continue
    
    return users

def display_branding():
    """Display branding information"""
    branding = """
    ╔═══════════════════════════════════════════╗
    ║              DARKBOSS1BD TOOLS            ║
    ║         Advanced Web Scraper v3.0         ║
    ╚═══════════════════════════════════════════╝
    """
    print(branding)
    print("Telegram ID: https://t.me/darkvaiadmin")
    print("Telegram Channel: https://t.me/windowspremiumkey")
    print("=" * 50)

def open_links():
    """Open all necessary links"""
    links = [
        "https://t.me/darkvaiadmin",
        "https://t.me/windowspremiumkey"
    ]
    
    print("[*] Opening branding links...")
    for link in links:
        try:
            webbrowser.open(link)
            time.sleep(1)
        except:
            print(f"[!] Failed to open {link}")

def generate_html_report(users, url, filename):
    """Generate a beautiful HTML report"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DarkBoss1BD Scraping Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #0d1117;
            color: #c9d1d9;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: #161b22;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.3);
        }}
        .header {{
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            color: white;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }}
        .header p {{
            margin: 5px 0 0;
            color: #f1f2f6;
            font-size: 1.2em;
        }}
        .info-box {{
            background-color: #21262d;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            border-left: 4px solid #ff6b6b;
        }}
        .user-card {{
            background: linear-gradient(135deg, #21262d 0%, #30363d 100%);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }}
        .user-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2);
        }}
        .user-avatar {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            object-fit: cover;
            border: 3px solid #ff6b6b;
            margin-right: 15px;
            float: left;
        }}
        .user-info {{
            margin-left: 100px;
        }}
        .user-name {{
            font-size: 1.4em;
            margin: 0 0 10px;
            color: #ff6b6b;
        }}
        .user-detail {{
            margin: 5px 0;
            font-size: 0.95em;
        }}
        .label {{
            font-weight: bold;
            color: #58a6ff;
            display: inline-block;
            width: 80px;
        }}
        .stats {{
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
            text-align: center;
        }}
        .stat-box {{
            background: linear-gradient(135deg, #21262d 0%, #30363d 100%);
            border-radius: 8px;
            padding: 15px;
            flex: 1;
            margin: 0 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #ff6b6b;
            margin: 0;
        }}
        .stat-label {{
            font-size: 0.9em;
            color: #8b949e;
            margin: 5px 0 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding: 15px;
            border-top: 1px solid #30363d;
            color: #8b949e;
            font-size: 0.9em;
        }}
        .branding {{
            background-color: #21262d;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            margin-top: 20px;
        }}
        .branding a {{
            color: #58a6ff;
            text-decoration: none;
            margin: 0 10px;
        }}
        .branding a:hover {{
            text-decoration: underline;
        }}
        .no-data {{
            text-align: center;
            padding: 40px;
            color: #8b949e;
            font-style: italic;
        }}
        .tips {{
            background-color: #21262d;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            border-left: 4px solid #58a6ff;
        }}
        .error-log {{
            background-color: #2d1e1e;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            border-left: 4px solid #ff6b6b;
            color: #ff9f9f;
            font-family: monospace;
            font-size: 0.9em;
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>DarkBoss1BD Web Scraper Report</h1>
            <p>Advanced User Information Extraction Tool</p>
        </div>
        
        <div class="info-box">
            <h2>Scraping Details</h2>
            <p><strong>Target URL:</strong> {url}</p>
            <p><strong>Scraping Date:</strong> {timestamp}</p>
            <p><strong>Total Users Found:</strong> {len(users)}</p>
        </div>
        
        <div class="stats">
            <div class="stat-box">
                <p class="stat-number">{len(users)}</p>
                <p class="stat-label">Users Found</p>
            </div>
            <div class="stat-box">
                <p class="stat-number">{sum(1 for user in users if 'email' in user)}</p>
                <p class="stat-label">Emails Collected</p>
            </div>
            <div class="stat-box">
                <p class="stat-number">{sum(1 for user in users if 'avatar' in user)}</p>
                <p class="stat-label">Avatars Found</p>
            </div>
        </div>
"""

    if users:
        html_content += "<h2>User Information</h2>"
        for i, user in enumerate(users, 1):
            avatar_html = f'<img src="{user["avatar"]}" class="user-avatar" alt="Avatar">' if 'avatar' in user else ''
            name = user.get('name', 'Unknown')
            email = user.get('email', 'Not available')
            username = user.get('username', 'Not available')
            bio = user.get('bio', 'No bio available')
            profile_url = user.get('profile_url', '#')
            
            html_content += f"""
            <div class="user-card">
                {avatar_html}
                <div class="user-info">
                    <h3 class="user-name">{name}</h3>
                    <p class="user-detail"><span class="label">Email:</span> {email}</p>
                    <p class="user-detail"><span class="label">Username:</span> {username}</p>
                    <p class="user-detail"><span class="label">Bio:</span> {bio}</p>
                    <p class="user-detail"><span class="label">Profile:</span> <a href="{profile_url}" target="_blank">{profile_url}</a></p>
                </div>
                <div style="clear: both;"></div>
            </div>
            """
    else:
        html_content += """
        <div class="no-data">
            <h2>No User Data Found</h2>
            <p>The scraper couldn't automatically detect user profiles on this website.</p>
        </div>
        
        <div class="tips">
            <h3>Tips for Better Results:</h3>
            <ul>
                <li>Try social media sites (Facebook, Twitter, Instagram) which have standardized profile structures</li>
                <li>Try forums or community websites with user profiles</li>
                <li>Try websites with author pages or member directories</li>
                <li>For custom websites, manual HTML analysis might be needed</li>
                <li>Some websites require authentication to access user data</li>
            </ul>
        </div>
        """

    html_content += f"""
        <div class="branding">
            <p>Report generated by <strong>DarkBoss1BD Tools</strong></p>
            <p>
                <a href="https://t.me/darkvaiadmin" target="_blank">Telegram ID</a> | 
                <a href="https://t.me/windowspremiumkey" target="_blank">Telegram Channel</a>
            </p>
        </div>
        
        <div class="footer">
            <p>© {datetime.now().year} DarkBoss1BD Tools. For educational purposes only.</p>
        </div>
    </div>
</body>
</html>
"""
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[+] HTML report generated: {filename}")
        return filename
    except Exception as e:
        print(f"[!] Failed to generate HTML report: {e}")
        return None

def save_results(users, filename):
    """Save results to a text file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("DarkBoss1BD Scraping Results\n")
            f.write("=" * 50 + "\n")
            f.write(f"Scraping Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            
            if users:
                for i, user in enumerate(users, 1):
                    f.write(f"User #{i}:\n")
                    for key, value in user.items():
                        f.write(f"  {key}: {value}\n")
                    f.write("\n")
            else:
                f.write("No user data found. Tips:\n")
                f.write("- Try social media sites (Facebook, Twitter, Instagram)\n")
                f.write("- Try forums or community websites\n")
                f.write("- Try websites with author pages\n")
                f.write("- For custom sites, manual HTML analysis might be needed\n")
                f.write("- Some websites require authentication to access user data\n")
        
        print(f"[+] Results saved to {filename}")
    except Exception as e:
        print(f"[!] Failed to save results: {e}")

def main():
    """Main program"""
    display_branding()
    time.sleep(2)
    open_links()
    time.sleep(3)
    
    print("\n[*] Starting advanced web scraping tool...")
    time.sleep(1)
    
    # Target URL
    target_url = input("\n[?] Enter target website URL: ").strip()
    
    if not target_url:
        print("[!] URL required")
        return
    
    # URL validation
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url
    
    # Scrape website using multiple methods
    users = scrape_users_from_website(target_url)
    
    # Save text results
    text_filename = f"darkboss_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    save_results(users, text_filename)
    
    # Generate HTML report
    html_filename = f"darkboss_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    html_file = generate_html_report(users, target_url, html_filename)
    
    # Open HTML report in browser
    if html_file:
        try:
            webbrowser.open('file://' + os.path.abspath(html_file))
            print("[+] HTML report opened in browser")
        except:
            print("[!] Could not open HTML report automatically")
    
    if users:
        print(f"[+] Found information for {len(users)} users")
        print("\n[+] Process completed successfully!")
    else:
        print("[!] No user information found with automated methods")
        print("[*] Try social media sites or community websites for better results")
        print("[*] Some websites require authentication or have anti-scraping measures")

if __name__ == "__main__":
    main()
