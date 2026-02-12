# Multi-Agent Detailed LLM Logging Guide

## Overview

이 가이드는 multi-agent orchestrator에서 각 agent의 LLM input/output을 상세하게 로깅하는 방법을 설명합니다.

## 기능

Detailed LLM logging을 활성화하면:

- ✅ **전체 프롬프트 캡처**: 모든 system + user 메시지
- ✅ **전체 응답 캡처**: LLM의 완전한 응답 텍스트
- ✅ **메타데이터**: 타임스탬프, 토큰 사용량, 모델 정보
- ✅ **Agent 구분**: planner, searcher, critic, browser-agent 별로 분리
- ✅ **Step 동기화**: orchestrator step number와 동기화
- ✅ **JSON 포맷**: 파싱하기 쉬운 구조화된 JSON

## 사용 방법

### 1. Config 파일에서 활성화

```yaml
logging:
  run_dir_base: runs/multiagent
  experiment_name: my_experiment
  save_screenshots: true
  save_dom_snapshots: true
  log_level: INFO
  detailed_llm_logging: true  # 이 줄을 추가하거나 true로 설정
```

### 2. 실행

```bash
# 예시 config 사용
uv run python running_dirs/run_multiagent.py \
  --task "네이버에서 날씨 검색" \
  --config configs/multiagent_detailed_logging_example.yaml
```

### 3. 로그 확인

실행 후 다음 디렉토리 구조가 생성됩니다:

```
runs/multiagent/
└── 20260212_143022_detailed_logging_test/
    ├── config.yaml                    # 사용된 config 파일 복사본
    ├── config_snapshot.json           # 파싱된 config (JSON)
    ├── run.log                        # Python 로그 출력
    ├── summary.json                   # 최종 실행 요약
    ├── steps/                         # Step 요약 로그
    │   ├── step_0000.json
    │   ├── step_0001.json
    │   └── ...
    ├── artifacts/                     # 스크린샷 등
    │   ├── step_0000_screenshot_...png
    │   └── ...
    └── detailed_llm_logs/             # ⭐ 새로운 상세 LLM 로그
        ├── step_0000_planner_call_1_20260212_143023_456.json
        ├── step_0000_browser-agent_call_1_20260212_143024_789.json
        ├── step_0001_searcher_call_1_20260212_143025_123.json
        ├── step_0001_planner_call_1_20260212_143026_456.json
        ├── step_0001_critic_call_1_20260212_143027_789.json
        └── ...
```

## 로그 파일 형식

각 detailed log 파일은 다음과 같은 JSON 구조를 갖습니다:

```json
{
  "timestamp": "2026-02-12T14:30:23.456789+00:00",
  "agent_name": "planner",
  "step_number": 1,
  "call_number": 1,
  "model": "Qwen3VL_32b",
  "provider": "vllm",
  "messages": [
    {
      "role": "system",
      "content": "You are a planner agent..."
    },
    {
      "role": "user",
      "content": "Current task: ...\n\nCurrent state: ..."
    }
  ],
  "output_format": null,
  "kwargs": {},
  "response": {
    "completion": "Let me analyze the current state...",
    "input_tokens": 1234,
    "output_tokens": 567,
    "model": "Qwen3VL_32b"
  },
  "success": true
}
```

### 파일명 규칙

```
step_{STEP:04d}_{AGENT_NAME}_call_{CALL_NUM}_{TIMESTAMP}.json
```

예시:
- `step_0000_planner_call_1_20260212_143023_456.json`
  - Step 0에서 planner agent의 첫 번째 LLM 호출
- `step_0005_browser-agent_call_2_20260212_143045_789.json`
  - Step 5에서 browser-agent의 두 번째 LLM 호출

## Agent 유형

로그에 나타나는 agent 이름:

- **planner**: 메인 action 결정 agent
- **searcher**: 정보 수집 agent (첫 step 또는 loop 감지 시)
- **critic**: action 검토 agent (항상 실행)
- **browser-agent**: 실제 브라우저 조작을 수행하는 browser-use Agent

## 이미지 처리

스크린샷이 포함된 메시지의 경우, base64 이미지는 가독성을 위해 truncate됩니다:

```json
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "Analyze this screenshot..."
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "data:image/png;base64,iVBORw0KG... [TRUNCATED 123456 chars]",
        "detail": "low"
      }
    }
  ]
}
```

실제 스크린샷은 `artifacts/` 디렉토리에 저장되며 step과 동기화됩니다.

## 디버깅 팁

### 1. 특정 step의 agent 통신 추적

```bash
# Step 3의 모든 agent 호출 확인
ls detailed_llm_logs/step_0003_*.json

# Step 3의 planner input 확인
jq '.messages' detailed_llm_logs/step_0003_planner_call_1_*.json

# Step 3의 critic 응답 확인
jq '.response.completion' detailed_llm_logs/step_0003_critic_call_1_*.json
```

### 2. Agent 간 정보 흐름 추적

```bash
# Searcher가 수집한 정보
jq -r '.response.completion' detailed_llm_logs/*searcher*.json

# Planner가 받은 입력 (searcher 정보 포함)
jq -r '.messages[] | select(.role=="user") | .content' \
  detailed_llm_logs/step_0001_planner*.json
```

### 3. 토큰 사용량 분석

```bash
# 모든 호출의 토큰 사용량 요약
jq -r '"\(.agent_name),\(.step_number),\(.response.input_tokens),\(.response.output_tokens)"' \
  detailed_llm_logs/*.json | column -t -s,
```

### 4. 에러 확인

```bash
# 실패한 호출 찾기
jq 'select(.success == false)' detailed_llm_logs/*.json
```

## 성능 고려사항

⚠️ **Warning**: Detailed logging은 대용량 텍스트를 디스크에 저장합니다.

- 각 LLM 호출마다 별도의 JSON 파일 생성
- 긴 프롬프트나 응답은 수백 KB가 될 수 있음
- 많은 step을 실행하면 수백 개의 파일이 생성됨

**권장사항**:
- 디버깅이 필요할 때만 활성화
- 프로덕션 환경에서는 비활성화
- 정기적으로 오래된 run 디렉토리 정리

## 구현 세부사항

이 기능은 **non-invasive monkey patching** 방식으로 구현되어:

- ✅ 기존 BaseAgent, Agent 코드 수정 최소화
- ✅ Config로 쉽게 enable/disable
- ✅ LLM wrapper를 통한 투명한 로깅
- ✅ 모든 LLM provider (vllm, azure, openai 등) 지원

관련 파일:
- `/home/user/browser-use/multiagent/detailed_logging.py` - LLM wrapper 구현
- `/home/user/browser-use/multiagent/config.py` - Config 스키마
- `/home/user/browser-use/multiagent/orchestrator.py` - Wrapper 통합

## 예시 분석 워크플로우

1. **문제 재현**: detailed logging 활성화하고 실행
2. **Step 식별**: 문제가 발생한 step 찾기 (summary.json 확인)
3. **Agent 순서 확인**: 해당 step의 모든 agent 로그 시간순 정렬
4. **Input 검사**: 각 agent가 받은 context 확인
5. **Output 검사**: 각 agent의 응답 확인
6. **정보 흐름 추적**: searcher → planner → critic → browser-agent 흐름 확인

이 방식으로 agent 간 통신 문제, 잘못된 context 전달, prompt 문제 등을 디버깅할 수 있습니다.
