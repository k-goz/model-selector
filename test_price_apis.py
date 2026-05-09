import urllib.request
import json
import os

proxy_handler = urllib.request.ProxyHandler({
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
})
opener = urllib.request.build_opener(proxy_handler)
urllib.request.install_opener(opener)

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=10)
        return res.read().decode('utf-8')
    except Exception as e:
        return f"Error: {e}"

print("1. Testing LiteLLM...")
llm = fetch("https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json")
print(llm[:100])

print("2. Testing SiliconFlow pricing API...")
sf = fetch("https://api.siliconflow.cn/v1/models")
if "Error" not in sf:
    sf_data = json.loads(sf)
    for m in sf_data.get('data', [])[:3]:
        print(m.get('id'), m.get('pricing'))
else:
    print(sf)
