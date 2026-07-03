# RTP(급속열처리) 공정 운영 표준

RTP(Rapid Thermal Processing)는 웨이퍼를 수초 내 고온으로 올려 도펀트 활성화·어닐링을 수행한다.

핵심 관리 파라미터
- peak_temp_C: 목표 1050℃. 관리 상한 1055℃. 상한 초과 시 도펀트 과확산으로 sheet resistance 변동.
- ramp_rate_Cps: 목표 75℃/s. 과도한 승온율은 웨이퍼 열응력·슬립 유발.
- soak_time_s: 목표 5초.

품질 연계
- sheet_res_ohm 계측 스펙 195~215Ω. peak_temp 상승은 sheet resistance 상향과 강한 상관.
- sheet resistance 스펙 이탈 로트는 재작업(rework) 또는 스크랩 판정.

이상 시 점검 순서
1. 램프 프로파일·peak_temp 트렌드(FDC) 확인
2. 챔버 파이로미터 캘리브레이션 이력 확인
3. 대조 설비(RTP-02) 대비 편차 비교
