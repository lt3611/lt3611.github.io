#!/usr/bin/env python3
import os, sys, re, subprocess

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORK_DIR, "zhibo.txt")

# 更换为目前国内极速、非常稳定的知名源
SOURCES = [
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.txt",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv4.m3u",
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
    "https://gitee.com/why006/TV/raw/master/output/result.txt"
]

def download(url):
    print(f"\n[尝试下载] {url}")
    # 加入更完整的请求头，防止被源站拦截
    cmd = ["curl", "-s", "-L", "--connect-timeout", "10", "--max-time", "30", 
           "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
           "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=35)
        text = r.stdout.decode("utf-8", errors="replace")
        print(f"[诊断] 下载返回字符数: {len(text)}")
        if len(text) < 100:
            print(f"[诊断] 警告: 字符太少，可能被拦截或源失效。内容: {text[:50]}")
        return text
    except Exception as e:
        print(f"[诊断] 下载失败异常: {e}")
        return ""

def parse_content(text):
    lines = set()
    if not text: return lines
    
    # 放宽正则，只要是 http 开头的，并且包含流媒体后缀，或者带有 .m3u8
    pattern = r'(https?://[^\s"\'<>]+?(?:\.m3u8|\.flv|\.mp4|\.ts)[^\s"\'<>]*)'
    
    if "#EXTM3U" in text:
        current_name = ""
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith("#EXTINF"):
                match = re.search(r',([^,]+)$', line)
                if match: current_name = match.group(1).strip()
            elif line.startswith("http") and current_name:
                if re.search(pattern, line, re.I):
                    lines.add(f"{current_name},{line}")
                current_name = ""
    else:
        for line in text.split('\n'):
            line = line.strip()
            if ',' in line and line.startswith("http"):
                if re.search(pattern, line, re.I):
                    lines.add(line)
            elif line.startswith("http") and re.search(pattern, line, re.I):
                lines.add(f"未知频道,{line}")
    return lines

def main():
    print(">>> 开始运行测试...")
    all_lines = set()

    for url in SOURCES:
        text = download(url)
        extracted = parse_content(text)
        print(f"[诊断] 成功提取: {len(extracted)} 条")
        all_lines.update(extracted)

    if len(all_lines) == 0:
        print("❌ 致命错误：没有提取到任何源，请检查上面的诊断信息。")
        # 写入一个警告信息供用户查看
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("未获取到源,#genre#\n请查看GitHub Actions日志,https://github.com\n")
        return

    print(f"\n>>> 总计聚合了 {len(all_lines)} 条源，开始分类...")

    cctv, weishi, difang, other = set(), set(), set(), set()
    
    for line in all_lines:
        name = line.split(',')[0].upper()
        if "CCTV" in name or "央视" in name:
            cctv.add(line)
        elif "卫视" in name:
            weishi.add(line)
        else:
            other.add(line)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("央视频道,#genre#\n")
        for l in sorted(list(cctv)): f.write(f"{l}\n")
        f.write("\n卫视频道,#genre#\n")
        for l in sorted(list(weishi)): f.write(f"{l}\n")
        f.write("\n其他频道,#genre#\n")
        for l in sorted(list(other)): f.write(f"{l}\n")

    print(f"✅ 生成完毕！央视 {len(cctv)} 个，卫视 {len(weishi)} 个。")

if __name__ == "__main__":
    main()
