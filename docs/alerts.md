# Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: User request latency above SLO
- Severity: critical
- Duration: 5 phút
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: P95 latency và SLO request thành công trong 3000 ms.
- Điều kiện và thời gian duy trì: `latency_p95_ms > 3000` liên tục 5 phút.
- Ảnh hưởng tới người dùng: Phản hồi chat chậm, timeout hoặc người dùng gửi lại request.
- Ba bước kiểm tra đầu tiên:
  1. Xác nhận P50/P95/P99 và TTFT trong đúng cửa sổ cảnh báo.
  2. Lọc các log `response_sent` có `latency_ms > 3000`, lấy `correlation_id`.
  3. Mở trace cùng correlation ID và so sánh thời gian retrieval với generation.
- Mitigation tạm thời: Giảm concurrency, vô hiệu hóa incident practice nếu đang bật, và dùng fallback retrieval khi upstream chậm.
- Owner: `llm-platform-oncall`

## Alert 2

- Tên: User request failure rate burns error budget
- Severity: critical
- Duration: 10 phút
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: SLO 99.5%, error budget 0.5% trong 28 ngày.
- Điều kiện và thời gian duy trì: `error_rate_pct > 0.5` liên tục 10 phút.
- Ảnh hưởng tới người dùng: Request trả lỗi và không nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra số `request_received`, `request_failed` và breakdown theo `error_type`.
  2. Lấy correlation ID từ một log lỗi đại diện và kiểm tra metadata request.
  3. Mở trace tương ứng để xác định retrieval hay generation phát sinh lỗi.
- Mitigation tạm thời: Chuyển sang fallback an toàn, giảm tải và rollback prompt nếu lỗi bắt đầu sau khi đổi label.
- Owner: `llm-platform-oncall`

## Alert 3

- Tên: Answer quality or retrieval success degraded
- Severity: warning
- Duration: 15 phút
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: Quality proxy tối thiểu 0.75 và retrieval success tối thiểu 90%.
- Điều kiện và thời gian duy trì: `quality_score_avg < 0.75` hoặc `retrieval_success_rate_pct < 90` liên tục 15 phút.
- Ảnh hưởng tới người dùng: Câu trả lời thiếu căn cứ, kém liên quan hoặc phải dùng fallback thường xuyên.
- Ba bước kiểm tra đầu tiên:
  1. So sánh quality score và retrieval success trước/sau thời điểm cảnh báo.
  2. Lọc log theo `feature`, `model`, `tool_success` và lấy correlation ID đại diện.
  3. Kiểm tra document previews, prompt version và generation trong trace liên quan.
- Mitigation tạm thời: Rollback label `production` về prompt baseline và bật fallback tài liệu cho feature bị ảnh hưởng.
- Owner: `ai-quality-oncall`
