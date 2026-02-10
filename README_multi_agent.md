# Multi-Agent Orchestration Guide (`README_multi_agent.md`)

이 문서는 최근 추가된 **multi-agent orchestration 확장 기능**(sequence 실행, 다양한 YAML 조합, 실행 스크립트)을 한 번에 이해하고 바로 실행할 수 있도록 정리한 가이드입니다.

---

## 1) 무엇이 추가되었나?

기존 browser-use는 단일 agent가 한 task를 step-by-step으로 수행하는 구조에 강점이 있습니다.
이번 확장은 그 위에 **orchestration layer**를 두어 다음을 가능하게 합니다.

- 여러 agent를 YAML로 정의/교체
- task를 여러 agent에게 분산 실행
- sequence 모드로 agent 실행 순서를 고정
- shell script로 실행 옵션을 쉽게 바꿔가며 실험

핵심 목적은 **"다양한 multi-agent 조립 실험"** 입니다.

---

## 2) 핵심 개념

### A. Sequence 모드

`sequence.enabled: true` 인 경우:

- 각 task를 `sequence.steps`에 정의된 **agent 이름 순서대로** 실행
- 이전 단계 결과를 다음 단계 컨텍스트로 전달 (`pass_context`)
- 실패 시 즉시 중단 여부 선택 (`stop_on_failure`)

예시: `planner -> navigator -> data_extractor`

### B. Non-sequence 모드

`sequence.enabled: false` 인 경우:

- task queue에서 꺼낸 task를 **idle 상태인 agent에게 할당**
- 기본은 "가용 agent 우선 할당"이며 고정 체인 실행이 아님
- 특정 agent로 강제하려면 `TaskConfig.assigned_agent` 사용

즉, sequence가 없으면 역할 체인이 자동으로 명시되지는 않고, 병렬/가용성 기반 실행이 중심입니다.

---

## 3) 추가/변경된 파일 요약

### 실행 편의

- `bin/run_orchestration.sh`
  - example/config 인자를 받아 실행하는 래퍼 스크립트
  - 내부적으로 `uv run python examples/multi_agent_orchestration.py ...` 호출

### 예제 진입점

- `examples/multi_agent_orchestration.py`
  - `--config` 옵션 지원
  - `BROWSER_USE_ORCHESTRATION_CONFIG` 환경변수 지원
  - `simple`, `complex`, `events`, `custom` 예제 선택 실행

### 실험용 YAML 프리셋

- `examples/orchestration_configs/sequence_planner_navigator.yaml`
  - sequence 기반 planner → navigator 체인
- `examples/orchestration_configs/research_validate_shared.yaml`
  - shared browser + researcher/validator 조합
- `examples/orchestration_configs/triad_planner_research_extractor.yaml`
  - planner/researcher/data_extractor 3-agent 조합

### 문서/설정 모델

- `browser_use/orchestration/README.md`
  - sequence/non-sequence 동작 설명 보강
- `browser_use/orchestration/views.py`
  - `SequenceConfig` 모델 추가 및 검증
- `browser_use/orchestration/service.py`
  - sequence 실행 루프/컨텍스트 전달 구현
- `browser_use/orchestration/agent_registry.py`
  - agent name 기반 조회 추가
- `browser_use/orchestration/__init__.py`
  - `SequenceConfig` export

---

## 4) 빠른 실행 방법

## 0) 준비

```bash
uv venv --python 3.11
source .venv/bin/activate
uv sync --all-extras --dev
```

필요한 API 키(예: `OPENAI_API_KEY`)를 환경변수로 설정합니다.

## 1) 기본 예제 실행

```bash
bin/run_orchestration.sh --example simple
```

## 2) 특정 YAML 조합으로 실행

```bash
bin/run_orchestration.sh \
  --example complex \
  --config examples/orchestration_configs/sequence_planner_navigator.yaml
```

## 3) 환경변수로 config 지정

```bash
export BROWSER_USE_ORCHESTRATION_CONFIG=examples/orchestration_configs/triad_planner_research_extractor.yaml
bin/run_orchestration.sh --example events
```

## 4) Python으로 직접 실행

```bash
uv run python examples/multi_agent_orchestration.py simple --config examples/orchestration_config.yaml
```

---

## 5) YAML 실험 포인트

아래 항목들을 바꿔가며 조합 실험을 할 수 있습니다.

- `agents`
  - role, system_prompt, max_steps, include_browser_actions
- `llm_providers`
  - provider_type, model_name, temperature, timeout
- `max_concurrent_agents`
  - 병렬성 제어
- `shared_browser`
  - agent 간 브라우저 공유 여부
- `sequence`
  - agent 실행 순서 강제 여부

실험 팁:

1. 먼저 non-sequence에서 agent/프롬프트 품질을 안정화
2. 이후 sequence로 고정 체인을 만들고 단계별 책임 분리
3. 마지막으로 `pass_context`, `stop_on_failure` 조정

---

## 6) 트러블슈팅

### 의존성 설치가 실패할 때

- 사내 프록시/터널 환경에서는 `uv sync`가 네트워크 에러를 낼 수 있습니다.
- 먼저 네트워크/프록시 설정을 확인한 뒤 재시도하세요.

### sequence 관련 검증 에러

- `sequence.steps` 에는 반드시 **agents에 정의된 name** 이 들어가야 합니다.
- 중복 step 이름은 허용되지 않습니다.

### 어떤 agent가 실행됐는지 확인하고 싶을 때

- `events` 예제(`--example events`)로 실행하면 task 시작/완료 로그를 바로 확인할 수 있습니다.

---


## 8) PR 올리기 전 최소 체크리스트

아래 순서로 확인하면 실험/리뷰 과정에서 반복되는 이슈를 줄일 수 있습니다.

1. 의존성 설치
   - `uv sync --all-extras --dev`
2. 빠른 코드 품질 점검
   - `./bin/lint.sh --quick`
3. orchestration 실행 sanity check
   - `bin/run_orchestration.sh --example simple`
4. sequence preset smoke test
   - `bin/run_orchestration.sh --example complex --config examples/orchestration_configs/sequence_planner_navigator.yaml`

> 네트워크/프록시 환경 이슈로 설치가 실패하면, `uv` 에러 로그와 함께 환경 정보를 PR에 같이 남겨 주세요.

---

## 7) 모델 선택 참고

Browser-Use 기본 권장 모델은 `ChatBrowserUse` 입니다.
다만 orchestration 예제 YAML은 현재 일반 provider 예시(OpenAI 등) 중심으로 구성되어 있으므로,
실제 운영에서는 프로젝트 환경에 맞게 provider 설정을 교체해서 사용하면 됩니다.

