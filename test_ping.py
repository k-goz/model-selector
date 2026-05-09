import urllib.request
def test(url):
    try:
        urllib.request.urlopen(url, timeout=3)
        return "SUCCESS"
    except Exception as e:
        return f"FAIL: {e}"

print("baidu:", test("https://www.baidu.com"))
print("aliyun:", test("https://help.aliyun.com"))
