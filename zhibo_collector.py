#!/usr/bin/env python3
"""
高质量直播源全自动采集与测速
包含：Gitee 动态抓取 + 优质备用源兜底 + 宽松测速
"""
import os, sys, re, json, subprocess
import concurrent.futures

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")
GITEE_TOKEN = os.environ.get("GITEE_TOKEN", "")

# 极优质的兜底源（国内大厂/高手维护）
FALLBACK_SOURCES = [
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv4.m3u"
]

def curl_cmd(url, timeout=10):
    cmd = ["curl", "-s", "-L", "--connect-timeout", "5", "--max-time", str(timeout), 
           "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout+2)
        return r.stdout.decode("utf-8", errors="replace")
    except: return ""

def get_gitee_sources():
    """从 Gitee 搜最新仓库并盲抓常见文件名"""
    sources = []
    if not GITEE_TOKEN:
        print("⚠️ 未配置 GITEE_TOKEN，跳过 Gitee 搜索。")
        return sources

    print(">>> 正在搜索 Gitee 最新 TV 仓库...")
    api = f"https://gitee.com/api/v5/search/repositories?q=iptv&sort=updated&direction=desc&per_page=5&access_token={GITEE_TOKEN}"
    try:
        res = json.loads(curl_cmd(api))
        if not isinstance(res, list): return sources
        repos = res
    except: return sources

    # 盲抓常见文件名
    common_files = ["live.txt", "iptv.txt", "tv.txt", "zhibo.txt", "live.m3u", "iptv.m3u", "tv.m3u"]
    
    for repo in repos:
        owner = repo.get("namespace", {}).get("path")
        name = repo.get("path")
        branch = repo.get("default_branch", "master")
        
        for f in common_files:
            raw_url = f"https://gitee.com/{owner}/{name}/raw/{branch}/{f}"
            # 试探性请求（只看状态码）
            code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5", raw_url], capture_output=True).stdout.decode().strip()
            if code == "200":
                print(f"  🎯 发现源: {owner}/{name}/{f}")
                sources.append(raw_url)
                break # 找到一个就不找了
    return sources

def parse_content(text):
    """提取直播直链并规范化为 频道名,URL 格式"""
    lines = set()
    if "#EXTM3U" in text:
        # M3U 格式解析
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
        # TXT 格式解析
        for line in text.split('\n'):
            line = line.strip()
            if ',' in line and line.startswith("http"):
                url = line.split(',', 1)[1].strip()
                if any(ext in url.lower() for ext in ['.m3u8', '.flv', '.mp4']):
                    lines.add(line)
    return list(lines)

def test_stream(line):
    """宽松测速：8秒超时，只要返回 200/206 就算存活"""
    if ',' not in line: return None
    url = line.split(',')[1].strip()
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
           "-r", "0-2048", "--connect-timeout", "5", "--max-time", "8", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=10)
        if r.stdout.decode().strip() in ["200", "206"]:
            return line
    except: pass
    return None

def main():
    print(">>> 1. 收集源头...")
    gitee_urls = get_gitee_sources()
    all_source_urls = FALLBACK_SOURCES + gitee_urls
    
    print(f"    准备从 {len(all_source_urls)} 个文件源中提取...")
    all_lines = set()

    for url in all_source_urls:
        print(f"    拉取: {url[:60]}...")
        content = curl_cmd(url)
        extracted = parse_content(content)
        print(f"      提取到 {len(extracted)} 条")
        all_lines.update(extracted)

    all_lines = list(all_lines)
    print(f">>> 2. 共提取到 {len(all_lines)} 条流，开始宽松测速...")

    valid_lines = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        futures = [pool.submit(test_stream, line) for line in all_lines]
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            res = future.result()
            if res: valid_lines.append(res)
            if i % 50 == 0: print(f"      进度: {i}/{len(all_lines)} (可用: {len(valid_lines)})")

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
