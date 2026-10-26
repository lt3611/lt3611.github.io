#!/usr/bin/env python3
import os, sys, re, subprocess

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")

# 🌟 纯正的 Gitee 优质源（包含国内高频维护的央视、卫视）
GITEE_SOURCES = [
    "https://gitee.com/lwr851/live/raw/master/live.txt",
    "https://gitee.com/hyx2230/IPTV/raw/master/tv.m3u",
    "https://gitee.com/why006/TV/raw/master/output/result.txt",
    "https://gitee.com/ganquanemail/iptv-api/raw/master/output/result.txt"
]

def download_gitee(url):
    print(f"\n[尝试下载] {url}")
    
    # 伪装的请求头，绕过 Gitee 的基础限制
    headers = [
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "-H", "Referer: https://gitee.com/",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ]
    
    # 1. 先尝试直连
    cmd = ["curl", "-s", "-L", "--connect-timeout", "10", "--max-time", "30"] + headers + [url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=35)
        text = r.stdout.decode("utf-8", errors="replace")
        
        # 如果内容太短，说明被 Gitee 拦截了
        if len(text) < 1000 or "violation" in text or "403" in text or "404" in text:
            print(f"  [诊断] Gitee 直连被拦截(长度:{len(text)})，启用代理强穿...")
            
            # 2. 走 ghproxy 代理（国内常用的加速节点，能完美绕过 Gitee 封锁）
            proxy_url = "https://ghproxy.net/" + url
            cmd_proxy = ["curl", "-s", "-L", "--connect-timeout", "10", "--max-time", "30"] + headers + [proxy_url]
            r_proxy = subprocess.run(cmd_proxy, capture_output=True, timeout=35)
            text_proxy = r_proxy.stdout.decode("utf-8", errors="replace")
            
            if len(text_proxy) > len(text):
                print(f"  [诊断] 代理强穿成功，获取字符数: {len(text_proxy)}")
                return text_proxy
                
        print(f"  [诊断] 下载成功，获取字符数: {len(text)}")
        return text
    except Exception as e:
        print(f"  [错误] 下载失败: {e}")
        return ""

def parse_content(text):
    """极其暴力的解析：无论格式多乱，只要包含 http 就抓出来"""
    lines = set()
    if not text: return lines
    
    current_name = "未知频道"
    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        
        # 如果遇到 #EXTINF 标签，提取频道名
        if line.startswith("#EXTINF"):
            match = re.search(r',([^,]+)$', line)
            if match: current_name = match.group(1).strip()
            continue
            
        # 查找 URL
        url_match = re.search(r'(https?://[^\s"\'<>]+)', line)
        if url_match:
            url = url_match.group(1)
            # 如果这行还有别的内容，把它当频道名（兼容 频道名,url 和 url,频道名）
            if not line.startswith("http"):
                name_candidate = line.replace(url, '').replace(',', '').strip()
                if name_candidate: current_name = name_candidate
                
            lines.add(f"{current_name},{url}")
            current_name = "未知频道"
    
    return lines

def main():
    print(">>> 开始 Gitee 强力采集...")
    all_lines = set()

    for url in GITEE_SOURCES:
        text = download_gitee(url)
        extracted = parse_content(text)
        print(f"  [诊断] 成功提取: {len(extracted)} 条")
        all_lines.update(extracted)

    print(f"\n>>> 共聚合了 {len(all_lines)} 条源，开始分类...")

    cctv, weishi, difang, other = set(), set(), set(), set()
    
    for line in all_lines:
        name = line.split(',')[0].upper()
        if "CCTV" in name or "央视" in name:
            cctv.add(line)
        elif "卫视" in name:
            weishi.add(line)
        elif any(k in name for k in ["北京", "上海", "广东", "深圳", "湖南", "浙江", "江苏"]):
            difang.add(line)
        else:
            other.add(line)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("央视频道,#genre#\n")
        for l in sorted(list(cctv)): f.write(f"{l}\n")
        f.write("\n卫视频道,#genre#\n")
        for l in sorted(list(weishi)): f.write(f"{l}\n")
        f.write("\n地方频道,#genre#\n")
        for l in sorted(list(difang)): f.write(f"{l}\n")
        f.write("\n其他频道,#genre#\n")
        for l in sorted(list(other)): f.write(f"{l}\n")

    print(f"✅ 生成完毕！央视提取到 {len(cctv)} 个，卫视 {len(weishi)} 个。")

if __name__ == "__main__":
    main()
