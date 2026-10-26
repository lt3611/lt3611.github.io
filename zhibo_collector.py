#!/usr/bin/env python3
import os, sys, re, subprocess
import concurrent.futures
import urllib.request
import urllib.parse

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")

# 🌟 终极稳定源（包含国内大牛日常维护的优质央视/卫视源）
# 如果以后失效，可以替换这里
SOURCES = [
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",  # 最全、更新最快
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u", # 知名项目输出
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt"     # 经典源
]

def fetch_url(url):
    """使用 urllib 自带重试机制下载"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    try:
        # 先试直连
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"    直连失败: {e}，尝试代理...")
        # 如果直连失败，走 GitHub 加速代理
        proxy_url = "https://ghproxy.net/" + url
        req_proxy = urllib.request.Request(proxy_url, headers=headers)
        try:
            with urllib.request.urlopen(req_proxy, timeout=15) as response:
                return response.read().decode('utf-8', errors='ignore')
        except:
            return ""

def parse_content(text):
    lines = set()
    if not text: return lines
    if "#EXTM3U" in text:
        current_name = ""
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith("#EXTINF"):
                match = re.search(r',([^,]+)$', line)
                if match: current_name = match.group(1).strip()
            elif line.startswith("http") and current_name:
                if any(ext in line.lower() for ext in ['.m3u8', '.flv', '.mp4']):
                    lines.add(f"{current_name},{line}")
                current_name = ""
    else:
        for line in text.split('\n'):
            line = line.strip()
            if ',' in line and line.startswith("http"):
                url = line.split(',', 1)[1].strip()
                if any(ext in url.lower() for ext in ['.m3u8', '.flv', '.mp4']):
                    lines.add(line)
    return lines

def test_stream(line):
    if ',' not in line: return None
    url = line.split(',')[1].strip()
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
           "-r", "0-1024", "--connect-timeout", "5", "--max-time", "8", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=10)
        if r.stdout.decode().strip() in ["200", "206"]:
            return line
    except: pass
    return None

def main():
    print(">>> 1. 开始拉取顶级源站...")
    all_lines = set()

    for url in SOURCES:
        print(f"    拉取: {url[:60]}...")
        content = fetch_url(url)
        extracted = parse_content(content)
        print(f"      提取到 {len(extracted)} 条")
        all_lines.update(extracted)

    all_lines = list(all_lines)
    print(f">>> 2. 共提取到 {len(all_lines)} 条流，开始测速...")

    valid_lines = []
    # 开启 50 个并发测速，速度飞快
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        futures = [pool.submit(test_stream, line) for line in all_lines]
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            res = future.result()
            if res: valid_lines.append(res)
            if i % 100 == 0: print(f"      进度: {i}/{len(all_lines)} (可用: {len(valid_lines)})")

    print(f">>> 3. 测速完成，存活 {len(valid_lines)} 条。开始分类...")

    cctv, weishi, other = [], [], []
    for line in valid_lines:
        name = line.split(',')[0].upper()
        if "CCTV" in name or "央视" in name:
            cctv.append(line)
        elif "卫视" in name:
            weishi.append(line)
        else:
            other.append(line)

    # 去重并写入
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("央视频道,#genre#\n")
        for l in sorted(list(set(cctv))): f.write(f"{l}\n")
        f.write("\n卫视频道,#genre#\n")
        for l in sorted(list(set(weishi))): f.write(f"{l}\n")
        f.write("\n其他频道,#genre#\n")
        for l in sorted(list(set(other))): f.write(f"{l}\n")

    print("✅ 生成完毕！")

if __name__ == "__main__":
    main()
