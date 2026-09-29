# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Văn Hưởng
- **MSSV:** 2A202602743
- **Lớp:** K4-L3A
- **Repository URL:**
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602743`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence            | Đường dẫn                             |
| ------------------- | ------------------------------------- |
| Pytest cuối         | `evidence/01-pytest.txt`              |
| Log validator       | `evidence/02-log-validator.txt`       |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log      | `evidence/04-structured-log.jsonl`    |
| PII redaction       | `evidence/05-pii-redaction.txt`       |
| Trace list          | `evidence/06-trace-list.png`          |
| Trace waterfall     | `evidence/07-trace-waterfall.png`     |
| Trace metadata      | `evidence/08a-trace-metadata.png`, `evidence/08b-generation-usage.png` |
| Prompt versions     | `evidence/09-prompt-versions.png`     |
| Prompt rollback     | `evidence/10a-production-v2.png`, `evidence/10b-production-v1-rollback.png`, `evidence/10c-rollback-final-labels.png` |
| Dashboard runtime   | `evidence/11-dashboard-overview.png`  |
| Incident metric     | `evidence/12-incident-metric.png`     |
| Incident log        | `evidence/13-incident-log.png`        |
| Incident trace      | `evidence/14-incident-trace.png`      |

## 3. Kết quả kỹ thuật

| Nội dung                | Baseline | Kết quả cuối | Nhận xét |
| ----------------------- | -------- | ------------ | -------- |
| `validate_logs.py`      | [80/100](evidence/00-cp1-baseline.txt) | [100/100](evidence/02-log-validator.txt) | 12 correlation ID, đủ metadata, 0 PII leak |
| `validate_dashboard.py` | 6/6      | [6/6](evidence/03-dashboard-validator.txt) | Đủ sáu panel, query, unit và threshold |
| `pytest`                |          | 27 passed    | Toàn bộ test pass sau CP2 |
| Số traces hợp lệ        | 0        | [10](evidence/06-trace-list.png) | Xác minh bằng Langfuse Observations API v2 |
| Số PII leak             | 0        | 0            | Kiểm tra trên structured log bằng validator độc lập |
| Latency P95 / TTFT P95  |          | 954 ms / 55 ms | Workload CP2, cửa sổ dashboard 60 phút |
| Retrieval success rate  |          | 100%         | 12/12 retrieval thành công trong log runtime |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware xóa context cũ ở đầu mỗi request, nhận `x-request-id` nếu đúng dạng `req-<8-hex>`, nếu không thì sinh ID mới bằng UUID. ID được bind vào `structlog`, lưu trong `request.state`, trả trong body và header `x-request-id`; header `x-response-time-ms` ghi thời gian xử lý.
- **Các metadata được ghi vào structured log:** `user_id_hash`, `session_id`, `feature`, `model`, `env` được bind trước event `request_received` để dùng thống nhất cho các log trong request.
- **Cách bảo đảm PII được scrub trước khi ghi:** Processor `scrub_event` duyệt toàn bộ record và các cấu trúc lồng nhau, thay email, số điện thoại Việt Nam, CCCD và thẻ thanh toán trước `JsonlFileProcessor` và `JSONRenderer`.
- **Cách kiểm chứng kết quả:** Chạy 2 request runtime (một ID truyền vào, một ID tự sinh), sau đó chạy `python scripts/validate_logs.py` đạt 100/100 với 0 PII leak; `python -m pytest -q` đạt 27 passed.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Chạy 10 request `/chat` với user/session test CP2 và correlation ID có tiền tố `req-c2`; sau khi flush, dùng Langfuse Observations API v2 lọc root observation `lab-agent-run` và nhận đúng 10 trace trong [trace list](evidence/06-trace-list.png).
- **Cấu trúc root/retrieval/generation observations:** Root `AGENT` có hai child cùng cấp là `RETRIEVER` và `GENERATION`. Generation ghi model, managed prompt, token usage, cost và TTFT; xem [waterfall](evidence/07-trace-waterfall.png), [metadata](evidence/08a-trace-metadata.png) và [generation usage](evidence/08b-generation-usage.png).
- **Cách nối trace với log:** `correlation_id` được bind vào structured log và metadata của root trace. Ví dụ `req-c2a00001` nối tới trace `67ce96455dfa12539736db82c11cfb92`.
- **Prompt name:** `day13-chat`.
- **Version/label baseline:** Version 1, labels `baseline` và `production` sau rollback.
- **Version/label candidate:** Version 2, label `candidate`.
- **Trace ID của mỗi version:** v1 baseline `6bd60e1c4d967d2b0fb954f4e8c04ce6`; v2 candidate `d7c63e816043e851a422d5496448048a`; production v2 `67ce96455dfa12539736db82c11cfb92`; production v1 sau rollback `90832867d539f5fbe392a52670ed9a2f`.
- **Cách promote và rollback `production`:** Gán `production` cho v2 và chạy request `req-c2a00001`, sau đó gán lại `production` cho v1 và chạy `req-c2a00002`. Trạng thái cuối được đọc lại qua API: `production -> v1`; xem [v2 đang production](evidence/10a-production-v2.png), [v1 sau rollback](evidence/10b-production-v1-rollback.png) và [trace sau rollback](evidence/10c-rollback-final-labels.png).

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard dùng `data/logs.jsonl`, time range 60 phút và refresh 30 giây. Sáu panel gồm latency/TTFT, traffic, errors/retrieval success, cost, tokens và quality. Workload CP2 ghi nhận P50 159 ms, P95/P99 954 ms, TTFT P95 55 ms, 12 request, error rate 0%, retrieval success 100%, tổng cost 0.025272 USD, 504 input tokens, 1,584 output tokens và quality proxy trung bình 0.81; xem [dashboard runtime](evidence/11-dashboard-overview.png).
- **SLO và lý do chọn:** [SLO](../config/slo.yaml) yêu cầu 99.5% request thành công trong tối đa 3000 ms trên cửa sổ 28 ngày. Ngưỡng 3000 ms trùng đường SLO của panel latency và coi cả lỗi lẫn request chậm là bad event phía người dùng.
- **Cách tính error budget:** Error budget là `100% - 99.5% = 0.5%`. Với 100.000 request, cho phép tối đa 500 bad request; quy đổi theo thời gian của 28 ngày là 3 giờ 21 phút 36 giây.
- **Ba alert và runbook tương ứng:** [Alert rules](../config/alert_rules.yaml) theo dõi P95 latency trên 3000 ms trong 5 phút, error rate trên 0.5% trong 10 phút, và quality dưới 0.75 hoặc retrieval success dưới 90% trong 15 phút. Cả ba gửi Slack `#llmops-alerts`; quy trình kiểm tra và mitigation nằm trong [runbook](../docs/alerts.md).

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Tôi tắt capture raw input/output ở root observation và chỉ ghi các preview đã giới hạn độ dài, qua PII scrubber, trong child observation. Cách này vẫn giữ đủ dữ liệu để điều tra retrieval và generation nhưng giảm nguy cơ đưa email, số điện thoại, CCCD hoặc số thẻ vào Langfuse. `correlation_id` được giữ trong metadata để nối trace với structured log mà không cần lưu nguyên văn nội dung nhạy cảm.
- **Một lỗi/blocker đã gặp:** Starter chỉ tạo root observation nên waterfall ban đầu không cho biết thời gian nằm ở retrieval hay generation. Ngoài ra, Langfuse Python SDK v4 dùng observation context và `update`, trong khi dummy client phục vụ chế độ không có Langfuse chưa hỗ trợ giao diện này.
- **Cách tìm nguyên nhân và xử lý:** Tôi đối chiếu waterfall với luồng `LabAgent.run`, xác định `retrieve()` và `FakeLLM.generate()` chưa được instrument. Tôi thêm hai child observation bằng `start_as_current_observation`: retrieval ghi số tài liệu và trạng thái thành công; generation ghi model, managed prompt, token usage, cost và TTFT. Dummy tracing client và tests được cập nhật cùng contract để ứng dụng vẫn chạy khi Langfuse không khả dụng. Sau đó tôi chạy lại workload và xác nhận waterfall có đúng quan hệ root → retrieval/generation.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics dùng để phát hiện triệu chứng và khoanh vùng thời gian, ví dụ P95/TTFT tăng, error rate tăng hoặc retrieval success giảm. Từ cửa sổ đó, tôi lọc structured log để lấy request bất thường cùng `correlation_id`, model, feature và latency. Tôi mở trace có cùng `correlation_id`, so sánh duration và status của retrieval với generation, rồi mới kết luận bước gây ảnh hưởng. Root cause chỉ hợp lệ khi metric, log và trace cùng chỉ về một request hoặc cùng khoảng sự cố.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt name/version/label cho biết chính xác cấu hình nào tạo ra một câu trả lời, giúp so sánh baseline v1 với candidate v2 và tránh ghi version giả trong code. Token và cost giúp phát hiện prompt dài hoặc output tăng bất thường. SLO 99.5% trong 3000 ms chuyển trải nghiệm người dùng thành ngưỡng đo được và error budget 0.5% quy định mức lỗi chấp nhận. Label `production` cho phép chuyển phiên bản mà không sửa source; khi candidate gây lỗi, chậm hoặc giảm chất lượng, có thể rollback về v1 và kiểm chứng bằng trace mới.
- **Điều quan trọng nhất đã học:** Monitoring LLM chỉ hữu ích khi mọi tín hiệu liên kết được với nhau và vẫn bảo vệ dữ liệu. Dashboard cho biết có vấn đề, log xác định request, trace chỉ ra bước retrieval hay generation, còn prompt version giải thích cấu hình nào đang chạy. Thiếu `correlation_id`, child observation hoặc PII protection thì chuỗi điều tra không đáng tin cậy.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** CP1 và CP2 đã hoàn thành về source, validator và runtime evidence. Ảnh danh sách trace `06` cần chụp lại với bộ lọc chỉ root observation và thấy tên project cá nhân. Phần challenge CP3, ba evidence `12`–`14`, repository URL và commit SHA cuối sẽ được điền sau khi nhận challenge chính thức và tạo commit nộp bài.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
