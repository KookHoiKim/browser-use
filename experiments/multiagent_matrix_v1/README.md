# Multi-Agent Matrix Experiment v1

이 실험은 **prompt variant × workflow variant** 조합을 체계적으로 검증하기 위한 패키지입니다.

## 목적

기존 default prompt + default workflow 중심 검증에서 벗어나,
아래 두 축을 조합해서 비교합니다.

1. Prompt 스타일 변경
2. Agent 조합/오케스트레이션 정책 변경

## 구조

- `matrix.yaml`: 조합 정의 (task set / prompt variant / workflow variant / run group)
- `prompts/`: 실험용 custom prompt들
- `run.sh`: 실험 실행 엔트리 (experiments 패턴 준수)
- `generated_configs/`: 실행 시 자동 생성되는 조합별 config
- `runners/matrix_runner.py`: 여러 실험에서 재사용 가능한 generic runner

## 빠른 실행

```bash
# smoke group 실행 (기본)
./experiments/multiagent_matrix_v1/run.sh
```

```bash
# dry-run으로 조합/생성 config만 확인
DRY_RUN=true ./experiments/multiagent_matrix_v1/run.sh
```

```bash
# 전체 조합 실행
GROUP=full_matrix HEADLESS=true ./experiments/multiagent_matrix_v1/run.sh
```

## 실행 순서 제안

1. `DRY_RUN=true`로 조합과 생성 config 확인
2. `smoke` 그룹으로 최소 검증
3. `full_matrix`로 본 실험 수행
4. 결과에서 성공률/평균 step/critic reject/시간 비교

## 확장 포인트

- Prompt variant 추가:
  - strict JSON schema discipline
  - multilingual browsing
  - uncertainty-aware evidence gathering
- Workflow variant 추가:
  - 마지막 단계에서만 critic 호출
  - N-step마다 critic 호출
  - 도메인 유형별 searcher 동적 on/off
