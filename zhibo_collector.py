#!/usr/bin/env python3
"""
TVBox 直播源自动采集与深度提取
功能：
  1. 从 tvbox.clbug.com 获取源列表
  2. 提取 lives 列表
  3. 深度解析：如果遇到套娃列表(txt/m3u)，自动下载并解析出里面真正的 .m3u8 流地址
  4. 生成纯粹的 zhibo.txt
"""
import json, sys, re, subprocess, os, time
import concurrent.futures
import urllib.parse
from urllib.parse import urljoin, urlparse

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")

def curl_cmd(url, timeout=10, extra_args=None):
    cmd = ["curl", "-s", "-L", "--connect-timeout", str(timeout), "--max-time", str(timeout*2), "-A", "Mozilla/5.0"]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout*2+5)
        return r.stdout.decode("utf-8", errors="replace")
    except:
        return ""

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

def check_url_speed(url, timeout=5):
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code},%{time_total}",
           "--connect-timeout", str(timeout), "--max-time", str(timeout*2),
           "-L", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout*2+2)
        res = r.stdout.decode().strip().split(",")
        if len(res) == 2 and res[0].startswith("2"):
            return int(float(res[1]) * 1000)
    except: pass
    return 99999

def extract_stream_urls(text, base_url):
    """
    从文本中提取真正的 m3u8/flv/mp4 地址及对应频道名
    兼容 M3U 格式 和 TXT(频道名,url) 格式
    """
    results = []
    lines = text.strip().split('\n')
    
    # 1. 如果是标准的 M3U 格式
    if '#EXTINF' in text:
        current_name = "未知频道"
        for line in lines:
            line = line.strip()
            if line.startswith('#EXTINF'):
                name_match = re.search(r',([^,]+)$', line)
                if name_match:
                    current_name = name_match.group(1).strip()
            elif line.startswith('http'):
                results.append((current_name, line))
                
    # 2. 如果是 TXT 格式 (频道名,url) 或直接是 url
    else:
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if ',' in line:
                parts = line.split(',', 1)
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith('http') and any(ext in url.lower() for ext in ['.m3u8', '.flv', '.mp4', '.ts']):
                    results.append((name, url))
            elif line.startswith('http') and any(ext in line.lower() for ext in ['.m3u8', '.flv', '.mp4']):
                results.append(("未知频道", line))
                
    # 3. 如果以上都没提取到，直接用正则去文本里暴力抓 m3u8
    if not results:
        urls = re.findall(r'(https?://[^\s"\'<>]+?\.(?:m3u8|flv|mp4))', text)
        for u in urls:
            results.append(("未知频道", u))
            
    return results

def resolve_live_source(item):
    """解析单条直播源，如果是套娃则深度提取"""
    url = item.get("url", "")
    name = item.get("name", "未知频道")
    group = item.get("group", "未分组")
    
    # 如果本身就是视频流，直接返回
    if any(ext in url.lower() for ext in ['.m3u8', '.flv', '.mp4', '.ts']):
        return [{"name": name, "url": url, "group": group}]
        
    # 如果是 txt 或 m3u 套娃
    if url.endswith('.txt') or url.endswith('.m3u') or url.endswith('.php') or '?' in url:
        content = curl_cmd(url, timeout=10)
        if content and ('#EXTINF' in content or 'http' in content):
            extracted = extract_stream_urls(content, url)
            return [{"name": n, "url": u, "group": group} for n, u in extracted]
            
    return []

def test_live_stream(live_item):
    url = live_item.get("url", "")
    if not url.startswith("http"): return None
    
    # 测试流是否存活（读前2KB）
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
           "-r", "0-2048", "--connect-timeout", "4", "--max-time", "6", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=8)
        code = r.stdout.decode().strip()
        if code.startswith("2"):
            return live_item
    except: pass
    return None

def main():
    print("开始采集...")
    # 获取源列表
    html = curl_cmd("https://tvbox.clbug.com/user.php", timeout=15)
    src_urls = re.findall(r'data-url="([^"]+)"', html)
    src_names = re.findall(r'<td class="td-name">([^<]+)</td>', html)
    sources = [(n.strip(), u.strip().replace("&amp;", "&")) for n, u in zip(src_names, src_urls) if u.strip()]

    # 测活 JSON
    available = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(check_url_speed, url): (name, url) for name, url in sources}
        for future in concurrent.futures.as_completed(futures):
            name, url = futures[future]
            if future.result() < 99999:
                available.append((name, url))
    print(f"可用 JSON 接口: {len(available)}")

    # 提取初始 lives
    raw_lives = {}
    for name, url in available:
        data = parse_json(curl_cmd(url))
        if not data: continue
        for l in (data.get("lives") or []):
            u = l.get("url", "").strip()
            if u.startswith("http") and u not in raw_lives:
                raw_lives[u] = {
                    "name": l.get("name", "未知"),
                    "url": u,
                    "group": l.get("group") or "未分组"
                }

    print(f"获取到 {len(raw_lives)} 个初始直播条目，开始深度解析...")

    # 深度解析套娃
    final_lives = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
        futures = [pool.submit(resolve_live_source, item) for item in raw_lives.values()]
        for future in concurrent.futures.as_completed(futures):
            res_list = future.result()
            for res in res_list:
                if res["url"] not in final_lives:
                    final_lives[res["url"]] = res

    print(f"深度解析后，得到 {len(final_lives)} 个真实视频流，正在测活...")

    # 测活真实视频流
    valid_lives = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        futures = [pool.submit(test_live_stream, l) for l in final_lives.values()]
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            res = future.result()
            if res:
                valid_lives.append(res)
            if i % 100 == 0: print(f"进度: {i}/{len(final_lives)} (可用: {len(valid_lives)})")

    # 写入 TXT
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

    print(f"\n采集完成！共 {len(valid_lives)} 个真实播放源。")

if __name__ == "__main__":
    main()
