import requests
import time

USERNAME = 'your_bright_data_username'
PASSWORD = 'your_bright_data_password'

PROXY_API_URL_TEMPLATE = 'https://brightdata.com/api/proxy/india?region={state}'  # Example API

STATES = ['karnataka', 'maharashtra', 'tamil_nadu', 'delhi', 'west_bengal']

def get_proxy(state):
    proxy_api_url = PROXY_API_URL_TEMPLATE.format(state=state)
    
    try:
        response = requests.get(proxy_api_url, auth=(USERNAME, PASSWORD))
        if response.status_code == 200:
            proxy_data = response.json()
            proxy_ip = proxy_data.get('proxy_ip')
            proxy_port = proxy_data.get('proxy_port')
            print(f"Proxy for {state}: {proxy_ip}:{proxy_port}")
            return proxy_ip, proxy_port
        else:
            print(f"Failed to retrieve proxy for {state}: {response.status_code}")
    except Exception as e:
        print(f"Error fetching proxy for {state}: {e}")
    
    return None, None

def fetch_youtube_with_proxy(proxy_ip, proxy_port):
    proxies = {
        'http': f'http://{proxy_ip}:{proxy_port}',
        'https': f'https://{proxy_ip}:{proxy_port}',
    }
    
    try:
        youtube_url = 'https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID'
        response = requests.get(youtube_url, proxies=proxies, timeout=10)
        
        if response.status_code == 200:
            print(f"Successfully accessed YouTube with proxy {proxy_ip}")
        else:
            print(f"Failed to access YouTube with proxy {proxy_ip}: {response.status_code}")
    except Exception as e:
        print(f"Error accessing YouTube with proxy {proxy_ip}: {e}")

def rotate_proxies_and_fetch_youtube():
    for state in STATES:
        print(f"\nSwitching to proxy for {state}...")
        proxy_ip, proxy_port = get_proxy(state)
        
        if proxy_ip and proxy_port:
            fetch_youtube_with_proxy(proxy_ip, proxy_port)
        else:
            print(f"Skipping {state} due to proxy error.")
        
        time.sleep(60) 

if __name__ == '__main__':
    rotate_proxies_and_fetch_youtube()
