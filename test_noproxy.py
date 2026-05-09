import urllib.request
try:
    print("Testing siliconflow...")
    req = urllib.request.Request("https://api.siliconflow.cn/v1/models", headers={'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
    print("SUCCESS")
except Exception as e:
    print("FAIL:", e)
