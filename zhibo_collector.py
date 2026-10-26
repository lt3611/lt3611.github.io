#!/usr/bin/env python3
import os, sys, re, subprocess

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")

# 🌟 国内 Gitee 最强的高频更新源 + GitHub 优质备用源
# 这些源里包含了国内专人维护的央视、卫视、地方台，全是国内直连
SOURCES = [
    "https://gitee.com/why006/TV/raw/master/output/result.txt",          # Gitee 知名高频更新
    "https://gitee.com/ganquanemail/iptv-api/raw/master/output/result.m3u", # Gitee 极速央视/卫视
    "https://gitee.com/wj0321/tvlive/raw/main/tvlive.txt",                # Gitee 经典源
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",    # 全网最全聚合
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt" # 经典 IPv4
]

def download(url):
    print(f"正在拉取: {url}")
    cmd = ["curl", "-s", "-L", "--connect-timeout", "10", "--max-time", "30", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=35)
        text = r.stdout.decode("utf-8", errors="replace")
        return text
    except Exception as e:
        print(f"  拉取失败: {e}")
        return ""

def parse_content(text):
    """直接提取流地址，不做任何测速限制"""
    lines = set()
    if not text: return lines
    
    if "#EXTM3U" in text:
        current_name = ""
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith("#EXTINF"):
                # 提取频道名
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
                if any(ext in line.lower() for ext in ['.m3u8', '.flv', '.mp4']):
                    lines.add(line)
    return lines

def main():
    print(">>> 开始全量拉取（无测速过滤模式）...")
    all_lines = set()

    for url in SOURCES:
        text = download(url)
        extracted = parse_content(text)
        print(f"  ✅ 提取到 {len(extracted)} 条")
        all_lines.update(extracted)

    print(f">>> 共聚合了 {len(all_lines)} 条源，开始分类...")

    cctv, weishi, difang, other = set(), set(), set(), set()
    
    for line in all_lines:
        name = line.split(',')[0].upper()
        if "CCTV" in name or "央视" in name:
            cctv.add(line)
        elif "卫视" in name:
            weishi.add(line)
        elif any(k in name for k in ["北京", "上海", "广东", "深圳", "湖南", "浙江", "江苏", "四川", "湖北", "河南"]):
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

    print(f"✅ 生成完毕！央视 {len(cctv)} 个，卫视 {len(weishi)} 个。")

if __name__ == "__main__":
    main()
