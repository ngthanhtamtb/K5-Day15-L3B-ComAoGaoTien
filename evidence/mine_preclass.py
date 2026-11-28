"""Đào data gián tiếp: tỉ lệ sai LẦN ĐẦU của câu hỏi giữa video (data pre-class của BTC).

Chạy:  python evidence/mine_preclass.py <đường dẫn thư mục data/preclass> [nguon: mặc định pre_post_post]
(Lưu ý: video_quiz chỉ có 7 dòng trong data BTC nên không đủ để đếm; pre_post_post có 1.970 dòng.)
Chỉ dùng thư viện chuẩn. KHÔNG commit dữ liệu gốc; trong repo chỉ giữ số tổng hợp (evidence/data-mining.md).

Cách đếm (ghi TRƯỚC khi nhìn kết quả):
  - Mẫu: các dòng answers.csv có nguon = pre_post_post (câu hỏi ôn tập sau học), lan_thu = 1 (lần trả lời đầu của học viên cho câu đó),
    was_correct là True hoặc False (bỏ dòng trống).
  - Đơn vị: một câu hỏi = giá trị cột ref. Tỉ lệ sai = số False / số lượt trả lời lần đầu.
  - "Câu có nhiều lượt": chỉ xét câu có ≥ MIN_N lượt trả lời lần đầu để tỉ lệ không dao động.
  - "Câu sai nhiều": tỉ lệ sai ≥ HIGH_WRONG.
Lưu ý khi diễn giải: tỉ lệ sai cao có thể do câu khó, đáp án chưa rõ hoặc nội dung bài chưa tốt — số này KHÔNG tự chứng minh
câu hỏi bị lỗi; nó chỉ cho biết có bao nhiêu câu mà phần lớn học viên trả lời sai ngay lần đầu, tức chỗ cần giảng viên kiểm lại.
"""
import csv
import os
import sys
from collections import defaultdict

MIN_N = 30
HIGH_WRONG = 0.5


def main(folder, nguon="pre_post_post"):
    path = os.path.join(folder, "answers.csv")
    per_q = defaultdict(lambda: [0, 0])   # ref -> [số lượt, số sai]
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["nguon"] != nguon or r["lan_thu"] != "1" or r["was_correct"] not in ("True", "False"):
                continue
            per_q[r["ref"]][0] += 1
            per_q[r["ref"]][1] += r["was_correct"] == "False"
    total = sum(n for n, _ in per_q.values())
    wrong = sum(w for _, w in per_q.values())
    big = {q: v for q, v in per_q.items() if v[0] >= MIN_N}
    high = {q: v for q, v in big.items() if v[1] / v[0] >= HIGH_WRONG}
    print("Lượt trả lời lần đầu (%s):" % nguon, total, "· sai:", wrong, "(%.1f%%)" % (100.0 * wrong / total if total else 0))
    print("Số câu hỏi:", len(per_q), "· câu có ≥%d lượt: %d" % (MIN_N, len(big)))
    print("Câu có ≥%d lượt và sai ≥%d%%: %d/%d" % (MIN_N, HIGH_WRONG * 100, len(high), len(big)))
    print("Top 10 câu sai nhiều nhất (ref · lượt · % sai):")
    for q, (n, w) in sorted(big.items(), key=lambda kv: -kv[1][1] / kv[1][0])[:10]:
        print("  %s · %d · %.0f%%" % (q, n, 100.0 * w / n))


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(*sys.argv[1:])
