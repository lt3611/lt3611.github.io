#!/usr/bin/env python3
"""
TVBox 直播源极速采集版 (限制源数量，高并发，极短超时)
"""
import json, sys, re, subprocess, os, time
import concurrent.futures

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")

# 核心限制参数（想抓更多源可以改这里）
MAX_SOURCES = 30       # 只抓取最快的30个源，防止卡死
TIMEOUT_SEC = 5        # 连接超时5秒
MAX_WORKERS = 100      # 测活并发100

def curl_cmd(url, timeout=TIMEOUT_SEC):
    cmd = ["curl", "-s", "-L", "--connect-timeout", str(timeout), "--max-time", str(timeout*1.5), 
           "-A", "Mozilla/5.0", "--max-filesize", "500000", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout*2)
        return r.stdout.decode("utf-8", errors="replace")
    except: return ""

def parse_json(raw):
    if not raw: return None
    raw = raw.lstrip('﻿'); raw = re.sub(r',(\s*[}\]])', r'\1', raw)
    try: return json.loads(raw, strict=False)
    except:
        s, e = raw.find('{'), raw.rfind('}')
        if s >= 0 and e > s:
            try: return json.loads(raw[s:e+1], strict=False)
            except: pass
    return None

def check_speed(url):
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code},%{time_total}",
           "--connect-timeout", "3", "--max-time", "5", "-L", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=6)
        res = r.stdout.decode().strip().split(",")
        if len(res) == 2 and res[0].startswith("2"):
            return int(float(res[1]) * 1000)
    except: pass
    return 99999

def extract_urls(text):
    """从套娃文本中精准提取真实 m3u8/flv/mp4，剔除内网IP"""
    urls = set()
    # 兼容 m3u8 和 txt 格式
    matches = re.findall(r'(https?://[^\s"\'<>]+?\.(?:m3u8|flv|mp4|ts)[^\s"\'<>]*)', text, re.I)
    for u in matches:
        if not any(ip in u for ip in ['192.168.', '127.0.0.', '10.', '172.16.']):
            urls.add(u)
    return list(urls)

def resolve_live(item):
    url = item.get("url", "")
    name = item.get("name", "未知频道")
    group = item.get("group", "未分组")
    
    # 本身是流，直接返回
    if any(ext in url.lower() for ext in ['.m3u8', '.flv', '.mp4', '.ts']):
        return [{"name": name, "url": url, "group": group}]
        
    # 是套娃，快速拉取解析
    if any(k in url.lower() for k in ['.txt', '.m3u', '.php', '?']):
        content = curl_cmd(url, timeout=6)
        if content:
            real_urls = extract_urls(content)
            if real_urls:
                return [{"name": name, "url": u, "group": group} for u in real_urls[:5]] # 每个套娃最多取5个
    return []

def test_live(live):
    url = live.get("url", "")
    if not url.startswith("http"): return None
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
           "-r", "0-1024", "--connect-timeout", "3", "--max-time", "5", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=6)
        if r.stdout.decode().strip().startswith("2"): return live
    except: pass
    return None

def main():
    print("开始采集...")
    # 1. 抓源
    html = curl_cmd("https://tvbox.clbug.com/user.php", timeout=10)
    src_urls = re.findall(r'data-url="([^"]+)"', html)
    src_names = re.findall(r'<td class="td-name">([^<]+)</td>', html)
    sources = [(n.strip(), u.strip().replace("&amp;", "&")) for n, u in zip(src_names, src_urls) if u.strip()]

    # 2. 并发测速，排序，截断
    available = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
        futures = {pool.submit(check_speed, url): (name, url) for name, url in sources}
        for future in concurrent.futures.as_completed(futures):
            name, url = futures[future]
            lat = future.result()
            if lat < 99999: available.append((name, url, lat))
    
    # 只保留最快的前 N 个
    available.sort(key=lambda x: x[2])
    available = available[:MAX_SOURCES]
    print(f"筛选出最快的 {len(available)} 个源进行解析...")

    # 3. 解析 lives
    raw_lives = {}
    for name, url, lat in available:
        data = parse_json(curl_cmd(url))
        if not data: continue
        for l in (data.get("lives") or []):
            u = l.get("url", "").strip()
            if u.startswith("http") and u not in raw_lives:
                raw_lives[u] = {"name": l.get("name", "未知"), "url": u, "group": l.get("group") or "未分组"}
    
    print(f"提取到 {len(raw_lives)} 个直播条目，开始深度解析与测活...")

    # 4. 深度解析
    final_lives = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        futures = [pool.submit(resolve_live, item) for item in raw_lives.values()]
        for future in concurrent.futures.as_completed(futures):
            for res in future.result():
                if res["url"] not in final_lives:
                    final_lives[res["url"]] = res

    # 5. 测活真实流
    valid_lives = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(test_live, l) for l in final_lives.values()]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_lives.append(res)

    # 6. 写入文件
    grouped = {}
    for live in valid_lives:
        g = re.sub(r'[,\n\r]', '', live["group"]).strip() or "未分组"
        if g not in grouped: grouped[g] = set()
        name = re.sub(r'[,\n\r]', '', live["name"]).strip()
        grouped[g].add(f"{name},{live['url']}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for group, lines in grouped.items():
            f.write(f"{group},#genre#\n")
            for line in lines:
                f.write(f"{line}\n")
            f.write("\n")

    print(f"\n采集完成！共提取 {len(valid_lives)} 个可用直链。")

if __name__ == "__main__":
    main()
