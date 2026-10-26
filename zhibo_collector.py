#!/usr/bin/env python3
"""
全自动 Gitee 源嗅探器
1. 自动搜索 Gitee 最近更新的 TV/IPTV 仓库
2. 自动通过 API 遍历仓库目录，找出所有的 txt/m3u 文件
3. 下载文件并提取 m3u8 直播流
4. 并发测速筛选，生成最终 zhibo.txt
"""
import os, sys, re, json, subprocess
import concurrent.futures

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")
GITEE_TOKEN = os.environ.get("GITEE_TOKEN", "")

def curl_cmd(url, timeout=10):
    cmd = ["curl", "-s", "-L", "--connect-timeout", str(timeout), "--max-time", str(timeout*2), "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout*2+5)
        return r.stdout.decode("utf-8", errors="replace")
    except: return ""

def get_gitee_repos():
    """搜索 Gitee 上最近更新的 TV/IPTV 仓库"""
    if not GITEE_TOKEN:
        print("⚠️ 未配置 GITEE_TOKEN，停止搜索。")
        return []
    
    repos_to_scan = []
    # 搜索两个关键词，各取前10个最新更新的仓库
    for keyword in ["tv", "iptv"]:
        api = f"https://gitee.com/api/v5/search/repositories?q={keyword}&sort=updated&direction=desc&per_page=10&access_token={GITEE_TOKEN}"
        try:
            res = json.loads(curl_cmd(api))
            if isinstance(res, list):
                repos_to_scan.extend(res)
        except: pass
    
    # 去重
    seen = set()
    unique_repos = []
    for r in repos_to_scan:
        full_name = r.get("full_name")
        if full_name and full_name not in seen:
            seen.add(full_name)
            unique_repos.append(r)
    return unique_repos

def scan_repo_for_sources(repo):
    """深入单个仓库，找出所有可能的 txt / m3u 文件"""
    owner = repo.get("namespace", {}).get("path")
    name = repo.get("path")
    branch = repo.get("default_branch", "master")
    
    # 1. 获取文件树
    tree_api = f"https://gitee.com/api/v5/repos/{owner}/{name}/git/trees/{branch}?recursive=1&access_token={GITEE_TOKEN}"
    res = curl_cmd(tree_api)
    if not res: return []
    
    try:
        tree_data = json.loads(res)
        tree = tree_data.get("tree", [])
    except: return []

    valid_urls = []
    # 2. 在文件树中寻找 .txt 或 .m3u 文件（排除 readme 等无关文件）
    for item in tree:
        path = item.get("path", "")
        if path.lower().endswith((".txt", ".m3u")):
            # 只找名字里带 tv / iptv / live / zhibo 的文件
            if any(k in path.lower() for k in ["tv", "iptv", "live", "zhibo"]):
                raw_url = f"https://gitee.com/{owner}/{name}/raw/{branch}/{path}"
                valid_urls.append(raw_url)
    
    if valid_urls:
        print(f"  🎯 在 {owner}/{name} 发现 {len(valid_urls)} 个潜在源文件")
    return valid_urls

def extract_urls_from_text(text):
    """从文本中暴力提取 http 开头的流媒体链接"""
    urls = set()
    # 匹配所有 m3u8, flv, mp4
    matches = re.findall(r'(https?://[^\s"\'<>]+?\.(?:m3u8|flv|mp4)(?:\?[^\s"\'<>]*)?)', text, re.I)
    for u in matches:
        if not any(ip in u for ip in ['192.168.', '127.0.0.', '10.', '172.16.']):
            urls.add(u)
    return urls

def test_stream(url):
    """并发测速"""
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
           "-r", "0-1024", "--connect-timeout", "3", "--max-time", "5", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=7)
        if r.stdout.decode().strip() in ["200", "206"]:
            return url
    except: pass
    return None

def main():
    print(">>> 1. 正在搜索 Gitee 最新更新的 TV 仓库...")
    repos = get_gitee_repos()
    print(f"    找到 {len(repos)} 个活跃仓库。")

    print(">>> 2. 正在嗅探仓库内的直播源文件...")
    source_files = []
    for repo in repos[:10]:  # 最多扫描前10个，防止超时
        print(f"  扫描: {repo.get('full_name')}")
        source_files.extend(scan_repo_for_sources(repo))
    
    # 去重
    source_files = list(set(source_files))
    print(f"    共找到 {len(source_files)} 个源文件，开始下载解析...")

    print(">>> 3. 正在提取真实播放流地址...")
    all_streams = set()
    for f in source_files:
        content = curl_cmd(f, timeout=8)
        if content:
            all_streams.update(extract_urls_from_text(content))
    
    all_streams = list(all_streams)
    print(f"    提取到 {len(all_streams)} 个未验证的直链。")

    print(">>> 4. 正在并发测速过滤死链...")
    valid_streams = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as pool:
        futures = [pool.submit(test_stream, url) for url in all_streams]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_streams.append(res)

    print(f"    测速完成，存活 {len(valid_streams)} 个直链！")

    # 5. 生成最终文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("未分组,#genre#\n")
        for url in valid_streams:
            # 从 URL 中尝试提取一个名字（由于只有 URL，名字先用域名代替）
            host = url.split("/")[2]
            f.write(f"{host},{url}\n")

    print("✅ 全自动嗅探采集完成！")

if __name__ == "__main__":
    main()
