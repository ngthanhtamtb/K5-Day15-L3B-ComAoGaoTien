"""Đo độ ổn định: chạy MỖI câu thử nhiều lần, so nhãn + mã đoạn giữa các lần.

Chạy (từ thư mục gốc dự án):
    python eval/stability.py --runs 3                 # cả bộ eval/benchmark.csv, mỗi câu 3 lần
    python eval/stability.py --runs 3 --only B05,B13  # chỉ vài câu
    python eval/stability.py --runs 3 --max-usd 12    # dừng khi chi ước tính (giá thật qua proxy) vượt ngưỡng

Ghi eval/stability-N.csv (một dòng mỗi câu) + eval/stability-N.md (tóm tắt). Không phải lượt `run-N` của eval:
KHÔNG thay cho cột `pass` chấm tay và không dùng để tính % đạt. Nó chỉ trả lời: cùng một đầu vào, hệ thống
có cho cùng nhãn và cùng mã đoạn mỗi lần không.

Hai số: ổn định nhãn (nhãn theo thứ tự) và ổn định nhãn + tập mã đoạn: tỉ lệ lần chạy trùng với kết quả xuất hiện nhiều nhất.
Câu `[TAO_*]` sinh nội dung mới mỗi lần nên chữ ký chỉ gồm mã đoạn.
Chỉ dùng thư viện chuẩn. Kho luôn là kho gốc (A3_NO_UPLOADS=1) để so sánh được giữa các lần.
"""
import argparse
import collections
import csv
import datetime
import glob
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "codebase"))

LABEL_RE = re.compile(r"\b(KHOP_NGUON|SAI_NGUON|THIEU_NGUON|TU_CHOI)\b")
SEG_RE = re.compile(r"\bD\d{2}-[SQ]\d{2}\b")
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00)}   # niêm yết BTC, USD / 1 triệu token
PROXY_FACTOR = 6.5   # chi thật qua proxy / giá niêm yết (cost/cost-estimate.md §5), ước tính


def signature(case_input, output):
    segs = tuple(sorted(set(SEG_RE.findall(output))))
    if case_input.startswith("[TAO_"):
        return ("", segs)
    labels = tuple(LABEL_RE.findall(output))
    return (">".join(labels), segs)


def read_benchmark():
    with open(os.path.join(ROOT, "eval", "benchmark.csv"), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def next_index():
    nums = [int(m.group(1)) for p in glob.glob(os.path.join(ROOT, "eval", "stability-*.csv"))
            if (m := re.search(r"stability-(\d+)\.csv$", p))]
    return max(nums, default=0) + 1


def cost_of(events):
    return sum((e.get("tokens_in") or 0) * PRICES.get(e.get("model"), (0, 0))[0]
               + (e.get("tokens_out") or 0) * PRICES.get(e.get("model"), (0, 0))[1]
               for e in events if e.get("kind") == "model") / 1e6


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", default="", help="danh sách id cách nhau dấu phẩy")
    ap.add_argument("--max-usd", type=float, default=12.0, help="ngưỡng chi ước tính theo giá thật qua proxy")
    ap.add_argument("--wait", type=float, default=0.0, help="nghỉ giữa hai lần gọi (giây)")
    args = ap.parse_args()
    os.environ["A3_NO_UPLOADS"] = "1"      # trước khi nạp tools: luôn đo trên kho gốc

    import agent
    import tracing

    rows = read_benchmark()
    if args.only:
        want = {x.strip() for x in args.only.split(",")}
        rows = [r for r in rows if r["id"] in want]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    idx = next_index()
    out_csv = os.path.join(ROOT, "eval", "stability-%d.csv" % idx)
    spent, stopped, results = 0.0, "", []
    for r in rows:
        sigs, errors = [], 0
        for k in range(args.runs):
            if spent * PROXY_FACTOR > args.max_usd:
                stopped = "dừng: chi ước tính %.2f USD vượt --max-usd %.2f (trước %s lần %d)" % (
                    spent * PROXY_FACTOR, args.max_usd, r["id"], k + 1)
                break
            tracing.begin(r["id"])
            try:
                out = agent.answer(r["input"])["output"]
            except Exception as exc:                 # lỗi gọi model: ghi nhận, không dừng cả lượt
                out, errors = "", errors + 1
                print("  %s lần %d lỗi: %s" % (r["id"], k + 1, str(exc)[:120]))
            _, events = tracing.end()
            spent += cost_of(events)
            if out:
                sigs.append(signature(r["input"], out))
            time.sleep(args.wait)
        if stopped and not sigs:
            break
        common = collections.Counter(sigs).most_common(1)
        share = common[0][1] / len(sigs) if sigs else 0.0
        lab_common = collections.Counter(x[0] for x in sigs).most_common(1)
        lab_share = lab_common[0][1] / len(sigs) if sigs else 0.0
        results.append({"id": r["id"], "type": r["type"], "lan_chay": len(sigs), "loi": errors,
                        "on_dinh_nhan": "%.2f" % lab_share, "on_dinh": "%.2f" % share, "so_chu_ky_khac_nhau": len(set(sigs)),
                        "chu_ky_pho_bien": "%s | %s" % (common[0][0][0], ",".join(common[0][0][1])) if common else "",
                        "chu_ky_khac": " ;; ".join("%s | %s" % (a, ",".join(b)) for a, b in set(sigs) if (a, b) != common[0][0]) if common else ""})
        print("%s: %d lần, ổn định nhãn %.2f, nhãn+mã đoạn %.2f (chi ước tính lũy kế %.2f USD)" % (r["id"], len(sigs), lab_share, share, spent * PROXY_FACTOR))
        if stopped:
            break

    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else ["id"])
        w.writeheader()
        w.writerows(results)
    full = [x for x in results if x["lan_chay"] == args.runs and not x["loi"]]
    stable = [x for x in full if x["on_dinh"] == "1.00"]
    stable_lab = [x for x in full if x["on_dinh_nhan"] == "1.00"]
    md = ["# Độ ổn định — stability-%d@%s" % (idx, stamp), "",
          "- Số lần chạy mỗi câu: %d · số câu đã chạy: %d / %d" % (args.runs, len(results), len(read_benchmark())),
          "- Câu cho đúng một **nhãn** ở mọi lần chạy: **%d / %d** (câu chạy đủ lần, không lỗi)" % (len(stable_lab), len(full)),
          "- Câu cho đúng một **nhãn + tập mã đoạn** ở mọi lần chạy: **%d / %d**" % (len(stable), len(full)),
          "- Chi ước tính (giá niêm yết × %.1f proxy): %.2f USD; giá niêm yết: %.2f USD" % (PROXY_FACTOR, spent * PROXY_FACTOR, spent)]
    if stopped:
        md.append("- **%s**" % stopped)
    md += ["", "Câu không ổn định:", ""]
    unstable = [x for x in full if x["on_dinh"] != "1.00"]
    md += ["- %s (%s): ổn định nhãn %s, nhãn+mã đoạn %s — chữ ký phổ biến `%s`, khác: `%s`" % (x["id"], x["type"], x["on_dinh_nhan"], x["on_dinh"], x["chu_ky_pho_bien"], x["chu_ky_khac"])
           for x in unstable] or ["- (không có)"]
    md += ["", "Lưu ý: chữ ký chỉ gồm nhãn + mã đoạn; không đo chất lượng câu chữ và không thay cho cột `pass` chấm tay."]
    with open(out_csv.replace(".csv", ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
