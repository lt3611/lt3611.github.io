#!/usr/bin/env python3
import os, sys, re, subprocess
import concurrent.futures

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")

# 🌟 扩充：收录全网最全、包含各种央视/卫视/地方台的顶级源
SOURCES = [
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",         # 极度全，大量央视
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",      # 经典 IPv4 稳定源
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv4.m3u", # 范明明的优质源
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u",  # Guovin 测速源
    "https://raw.githubusercontent.com/zbefine/iptv/main/live.txt"             # 备选高频更新源
]

def download(url):
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
                # 兼容更多的流后缀
                if any(ext in line.lower() for ext in ['.m3u8', '.flv', '.mp4', '.ts']):
                    lines.add(f"{current_name},{line}")
                current_name = "未知频道"
    else:
        for line in text.split('\n'):
            line = line.strip()
            if ',' in line and line.startswith("http"):
                if any(ext in line.lower() for ext in ['.m3u8', '.flv', '.mp4', '.ts']):
                    lines.add(line)
    return lines

def test_stream(line):
    """优化测速：去掉 -r 0-1024，只判断状态码，防止误杀不支持的源"""
    if ',' not in line: return None
    url = line.split(',')[1].strip()
    
    # 去掉 -r 0-1024，很多源不支持 Range 请求，只要返回 200/302 就认为源存活
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
           "--connect-timeout", "5", "--max-time", "8", "-A", "Mozilla/5.0", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=10)
        code = r.stdout.decode().strip()
        if code in ["200", "302", "301", "206"]:
            return line
    except: pass
    return None

def main():
    print(">>> 开始拉取多个顶级源...")
    all_lines = set()

    for url in SOURCES:
        text = download(url)
        extracted = parse_text(text)
        print(f"  提取到 {len(extracted)} 条源")
        all_lines.update(extracted)

    all_lines = list(all_lines)
    print(f">>> 共需测试 {len(all_lines)} 条源，开始测速（耗时较长请耐心等待）...")

    valid_lines = []
    # 并发调高到 100，加快测速
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as pool:
        futures = [pool.submit(test_stream, line) for line in all_lines]
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            res = future.result()
            if res: valid_lines.append(res)
            if i % 200 == 0: print(f"  已测 {i} 条，存活 {len(valid_lines)} 条...")

    print(f">>> 测速完成，存活 {len(valid_lines)} 条。开始分类...")

    # 精细化分类
    cctv, weishi, difang, other = [], [], [], []
    for line in valid_lines:
        name = line.split(',')[0].upper()
        if "CCTV" in name or "央视" in name:
            cctv.append(line)
        elif "卫视" in name:
            weishi.append(line)
        elif any(k in name for k in ["北京", "上海", "广东", "深圳", "湖南", "浙江", "江苏", "四川", "湖北", "河南"]):
            difang.append(line)
        else:
            other.append(line)

    # 排序去重（让同频道的多个源排在一起）
    cctv = sorted(list(set(cctv)))
    weishi = sorted(list(set(weishi)))
    difang = sorted(list(set(difang)))
    other = sorted(list(set(other)))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("央视频道,#genre#\n")
        for l in cctv: f.write(f"{l}\n")
        
        f.write("\n卫视频道,#genre#\n")
        for l in weishi: f.write(f"{l}\n")
        
        f.write("\n地方频道,#genre#\n")
        for l in difang: f.write(f"{l}\n")
        
        f.write("\n其他频道,#genre#\n")
        for l in other: f.write(f"{l}\n")

    print("✅ 生成完毕！")

if __name__ == "__main__":
    main()
