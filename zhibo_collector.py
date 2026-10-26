#!/usr/bin/env python3
"""
从 Gitee 自动搜索最新 TV 源并测速
"""
import os, sys, re, json, subprocess
import concurrent.futures
import urllib.parse

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")
GITEE_TOKEN = os.environ.get("2a2b48d0b3e088ecfbac9bdbdf50c362", "")

def curl_cmd(url, timeout=10, extra_args=None):
    cmd = ["curl", "-s", "-L", "--connect-timeout", str(timeout), "--max-time", str(timeout*2), "-A", "Mozilla/5.0"]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout*2+5)
        return r.stdout.decode("utf-8", errors="replace")
    except: return ""

def search_gitee():
    """调用 Gitee API 搜索 TV 并获取最近更新的仓库"""
    print("正在搜索 Gitee 最新更新的 TV 仓库...")
    if not GITEE_TOKEN:
        print("⚠️ 未配置 GITEE_TOKEN，使用默认高质量静态源...")
        return ["https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt"] # 兜底源

    # 搜索 q=tv, 按 updated 降序
    api_url = f"https://gitee.com/api/v5/search/repositories?q=tv&sort=updated&direction=desc&per_page=10&access_token={GITEE_TOKEN}"
    resp = curl_cmd(api_url)
    
    try:
        repos = json.loads(resp)
        if not isinstance(repos, list):
            print("Gitee API 返回异常，可能 Token 错误或请求受限")
            return []
    except:
        print("Gitee API 解析失败")
        return []

    source_urls = []
    # 遍历搜出来的前几个仓库，去里面碰运气找常见的直播源文件名
    for repo in repos[:5]:
        owner = repo.get("namespace", {}).get("path")
        name = repo.get("path")
        branch = repo.get("default_branch", "master")
        
        # 常见的开源直播源命名
        possible_files = ["live.txt", "iptv.txt", "tv.txt", "zhibo.txt", "live.m3u", "iptv.m3u"]
        for f in possible_files:
            raw_url = f"https://gitee.com/{owner}/{name}/raw/{branch}/{f}"
            # 试探性请求，看看文件存不存在
            code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", raw_url], capture_output=True).stdout.decode()
            if code == "200":
                print(f"✅ 找到源文件: {owner}/{name}/{f}")
                source_urls.append(raw_url)
                break # 找到一个就不找其他的了
    return source_urls

def test_stream(line):
    if ',' not in line: return None
    url = line.split(',')[1].strip()
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
           "-r", "0-1024", "--connect-timeout", "3", "--max-time", "5", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=7)
        if r.stdout.decode().strip() in ["200", "206"]:
            return line
    except: pass
    return None

def main():
    sources = search_gitee()
    if not sources:
        print("❌ 没找到任何可用源，任务结束。")
        return

    print(f"共找到 {len(sources)} 个源文件，开始抓取解析...")
    all_lines = set()

    for src in sources:
        content = curl_cmd(src)
        if not content: continue
        
        # 解析 M3U
        if "#EXTM3U" in content:
            current_name = ""
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith("#EXTINF"):
                    match = re.search(r',([^,]+)$', line)
                    if match: current_name = match.group(1).strip()
                elif line.startswith("http") and current_name:
                    all_lines.add(f"{current_name},{line}")
                    current_name = ""
        # 解析 TXT
        else:
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith("http") and ',' in line:
                    all_lines.add(line)

    print(f"共提取 {len(all_lines)} 条源，开始并发测速...")

    valid_lines = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as pool:
        futures = [pool.submit(test_stream, line) for line in all_lines]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_lines.append(res)

    print(f"测速完成，存活 {len(valid_lines)} 条。写入文件...")

    cctv, weishi, other = [], [], []
    for line in valid_lines:
        name = line.split(',')[0]
        if "CCTV" in name.upper() or "央视" in name:
            cctv.append(line)
        elif "卫视" in name:
            weishi.append(line)
        else:
            other.append(line)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("央视,#genre#\n")
        for l in sorted(list(set(cctv))): f.write(f"{l}\n")
        f.write("\n卫视,#genre#\n")
        for l in sorted(list(set(weishi))): f.write(f"{l}\n")
        f.write("\n其他,#genre#\n")
        for l in sorted(list(set(other))): f.write(f"{l}\n")

    print("✅ 搞定！")

if __name__ == "__main__":
    main()
