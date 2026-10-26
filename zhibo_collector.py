#!/usr/bin/env python3
import os, sys, re, subprocess
import concurrent.futures

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")

# 国内公认最优质的三个源
SOURCES = [
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u",
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt"
]

def download(url):
    """用 curl 下载文本，最稳定，不会报 Python 环境错误"""
    print(f"正在下载: {url}")
    cmd = ["curl", "-s", "-L", "--connect-timeout", "10", "--max-time", "30", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=35)
        text = r.stdout.decode("utf-8", errors="replace")
        print(f"  下载完成，长度: {len(text)} 字符")
        return text
    except Exception as e:
        print(f"  下载失败: {e}")
        return ""

def parse_text(text):
    """提取直链"""
    lines = set()
    if not text: return lines
    if "#EXTM3U" in text:
        current_name = "未知频道"
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith("#EXTINF"):
                match = re.search(r',([^,]+)$', line)
                if match: current_name = match.group(1).strip()
            elif line.startswith("http") and current_name:
                if ".m3u8" in line or ".flv" in line:
                    lines.add(f"{current_name},{line}")
                current_name = "未知频道"
    else:
        for line in text.split('\n'):
            line = line.strip()
            if ',' in line and line.startswith("http"):
                if ".m3u8" in line or ".flv" in line:
                    lines.add(line)
    return lines

def test_stream(line):
    """测速"""
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
    print(">>> 开始运行...")
    all_lines = set()

    for url in SOURCES:
        text = download(url)
        extracted = parse_text(text)
        print(f"  提取到 {len(extracted)} 条源")
        all_lines.update(extracted)

    all_lines = list(all_lines)
    print(f">>> 共需测试 {len(all_lines)} 条源，开始并发测速...")

    valid_lines = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        futures = [pool.submit(test_stream, line) for line in all_lines]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_lines.append(res)

    print(f">>> 测速完成，存活 {len(valid_lines)} 条。开始分类...")

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
