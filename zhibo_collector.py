#!/usr/bin/env python3
import os, sys, re, subprocess

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")

# 🌟 只保留经过国内网友长期验证、可用率极高的顶级源
SOURCES = [
    # ① Guovin 的每日测速结果（剔除海外不可用，国内极速）
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.txt",
    # ② 经典的国内 IPv4 优选源（专为国内网络优化）
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
    # ③ YanG 的精选聚合（备用）
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u"
]

def download(url):
    cmd = ["curl", "-s", "-L", "--connect-timeout", "10", "--max-time", "30", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=35)
        return r.stdout.decode("utf-8", errors="replace")
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
                if any(ext in line.lower() for ext in ['.m3u8', '.flv', '.mp4']):
                    lines.add(line)
    return lines

def main():
    print(">>> 开始拉取高质量纯净源...")
    all_lines = set()

    for url in SOURCES:
        print(f"正在下载: {url}")
        text = download(url)
        extracted = parse_content(text)
        print(f"  提取到 {len(extracted)} 条")
        all_lines.update(extracted)

    print(f">>> 共聚合了 {len(all_lines)} 条源，开始分类...")

    cctv, weishi, difang, other = set(), set(), set(), set()
    
    for line in all_lines:
        name = line.split(',')[0].upper()
        # 强制清洗掉名字里乱码或者乱七八糟的源
        if not re.search(r'[\u4e00-\u9fa5A-Za-z0-9]', name): continue
        
        if "CCTV" in name or "央视" in name:
            cctv.add(line)
        elif "卫视" in name:
            weishi.add(line)
        elif any(k in name for k in ["北京", "上海", "广东", "深圳", "湖南", "浙江", "江苏", "四川", "湖北", "河南"]):
            difang.add(line)
        else:
            other.add(line)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        # 把央视和卫视放在最前面
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
