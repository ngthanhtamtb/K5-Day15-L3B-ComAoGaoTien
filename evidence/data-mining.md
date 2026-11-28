# Đào data — cách đếm và kết quả

> **Trạng thái:** đây là lần **thăm dò**, không tính là nguồn bằng chứng pain (lý do ở mục 5). Bằng chứng chính của nhóm là khảo sát (`evidence/survey/`, `evidence/summary.md`).
> Script ở `evidence/mine_preclass.py`; người khác chạy lại phải ra cùng số. Repo chỉ chứa số tổng hợp và mã câu hỏi, không chép lại data gốc của BTC.

## 1. Cách đếm

- Data dùng: `answers.csv` trong data pre-class của BTC (`data/preclass/`), 3.776 dòng dữ liệu, cột `created_at` từ **05/11/2026 đến 25/11/2026**. Không commit file gốc.
- Đếm gì: tỉ lệ trả lời **sai ở lần đầu** của từng câu hỏi ôn tập sau học · trên tập nào: dòng có `nguon = pre_post_post` (1.970 dòng; các nguồn khác: `chat` 1.260, `thuc_hanh` 519, `giai_thich` 20, `video_quiz` 7) · lọc gì: `lan_thu = 1` (lần trả lời đầu của học viên cho câu đó) và `was_correct` là `True` hoặc `False` (bỏ dòng trống).
- **Mẫu số là gì:** số lượt trả lời lần đầu hợp lệ của câu đó. Câu hỏi = giá trị cột `ref`. Chỉ xét "câu có nhiều lượt" khi có **≥ 30 lượt** trả lời lần đầu, để tỉ lệ không dao động. "Câu sai nhiều" = tỉ lệ sai ≥ 50%.
- Script / công thức: `python evidence/mine_preclass.py <thư mục data/preclass>` (chỉ dùng thư viện chuẩn của Python).
- **Ai viết cách đếm, khi nào:** cách đếm này nằm trong phần đầu script `evidence/mine_preclass.py`, do Claude Code (công cụ AI nhóm dùng) viết ngày 28/11/2026 trước khi chạy script, không phải nhóm đặt trước từ ngày đầu. Vì vậy đây là phép đếm thăm dò, không phải phép kiểm giả thuyết viết trước.
- `video_quiz` chỉ có 7 dòng nên không đếm được; đó là loại câu hỏi bật lên giữa video mà lát cắt ban đầu quan tâm.

## 2. Đọc trước, đếm sau

Đã đọc từ điển cột (`column_dictionary.csv`) và hai dòng đầu của `answers.csv` trước khi viết script (đọc xong mới định nghĩa thứ cần đếm; chưa đọc kỹ 30–50 dòng như guide khuyên). Các *kiểu* hành vi thấy được trong `answers.csv`:
- Học viên trả lời câu ôn tập sau học (`pre_post_post`), có đúng / sai và số lần thử.
- Học viên nhắn chat với AI (`chat`, không chấm đúng / sai), làm thực hành (`thuc_hanh`), tự giải thích (`giai_thich`).
- Câu bật lên giữa video (`video_quiz`) rất ít (7 dòng).

## 3. Kết quả

Chạy lại ngày 28/11/2026, ra đúng các số dưới đây:

| Đếm gì | x / N | % | Ghi chú |
|---|---|---|---|
| Lượt trả lời lần đầu bị sai (`pre_post_post`) | 399 / 1.968 | 20,3% | 1.970 dòng `pre_post_post`, 2 dòng bị loại (không phải lần đầu hoặc không chấm đúng / sai) |
| Câu hỏi có ≥ 30 lượt trả lời lần đầu | 12 / 156 | 7,7% | 156 câu hỏi khác nhau; phần lớn câu ít lượt nên không đo được |
| Câu có ≥ 30 lượt và sai ≥ 50% | 0 / 12 | 0% | Không câu nào quá nửa học viên sai ngay lần đầu |

## 4. ≥5 ví dụ cụ thể (mã câu hỏi `ref`, lần đầu, câu có ≥ 30 lượt)

Top 5 câu sai nhiều nhất (`ref` · số lượt · % sai):

1. `d01-on-chatbot-la-ung-dung` · 41 · 39%
2. `d01-on-chon-tang-model` · 35 · 23%
3. `d01-on-ba-yeu-to-hoi-tu` · 40 · 20%
4. `d01-on-so-lan-chay-vong-lap` · 40 · 20%
5. `d01-on-temperature-khong-sua-sai` · 36 · 19%

(Top 10 đầy đủ có trong kết quả chạy script; câu thứ 10 là `d01-on-tu-tin-khong-phai-dung`, 6%.)

## 5. Giới hạn của data

Data cho biết người ta **làm gì**, không cho biết **vì sao**. Thiếu gì, lệch về phía nào:
- Đây là kết quả của **học viên** làm bài ôn tập, không phải của **giảng viên** kiểm bài giảng, nên **không đo được pain của người dùng chính**. Tỉ lệ sai cao có thể do câu khó, đáp án chưa rõ hoặc nội dung bài chưa tốt; số này không tự chứng minh câu hỏi bị lỗi.
- Không có câu nào sai ≥ 50% với ≥ 30 lượt, nên data này **không cho thấy** đáp án / câu hỏi hỏng nhiều. Cũng không chứng minh là không hỏng.
- Các câu trong top 10 đều thuộc bài buổi 1 (mã `d01-`); phân bố theo buổi của toàn bộ 156 câu chưa kiểm.
- `video_quiz` (loại câu hỏi giữa video) chỉ có 7 dòng nên không đào được.

→ Kiểm lại bằng khảo sát người làm bài giảng (`evidence/survey/`, 20 hợp lệ / 23 phiếu): khảo sát hỏi trực tiếp việc kiểm bài giảng, nên đó mới là nguồn chính. Nhóm **không** tính data pre-class là nguồn đạt ngưỡng.
