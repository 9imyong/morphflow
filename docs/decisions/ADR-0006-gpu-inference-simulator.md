---
id: ADR-0006
title: 실제 GPU 대신 추론 시뮬레이터 사용
status: 승인됨
date: 2026-03-10
decision_makers: [김용준]
related_requirements: [REQ-platform-001]
supersedes: null
superseded_by: null
---

# ADR-0006: 실제 GPU 대신 추론 시뮬레이터 사용

## 맥락

이 시스템의 검증 대상은 추론 모델의 품질이 아니라 **병목이 생겼을 때의 구조적 대응**입니다. 필요한 것은 조절 가능한 지연, 제한된 동시성, 재현 가능한 실패율이며 실제 GPU는 이 중 어느 것도 실험 목적으로 제어하기 어렵습니다.

## 결정 기준

- 병목 상황을 재현 가능하게 만들 수 있는가
- 부하 실험에서 조건을 통제할 수 있는가
- 실제 추론으로 교체할 때 구조 변경이 최소인가

## 검토한 대안

### 대안 1: 실제 모델과 GPU 사용

- 장점: 실제 처리 특성 반영
- 단점: GPU 확보 필요. 지연과 실패를 실험 조건으로 통제 불가
- 위험: 검증 목적과 무관한 변수가 결과를 흔듦

### 대안 2: 고정 지연 더미 처리기

- 장점: 가장 단순
- 단점: 동시성 제한, 배치 처리, 실패율을 표현할 수 없음
- 위험: GPU 병목 특유의 현상을 재현하지 못함

### 대안 3: 특성을 재현하는 시뮬레이터

- 장점: 지연·동시성·실패율·마이크로배치를 설정으로 통제. 요청 단위 재정의도 가능
- 단점: 시뮬레이터 자체를 구현하고 유지해야 함
- 위험: 시뮬레이션 결과를 실제 성능으로 오해할 수 있음

## 결정

대안 3을 채택합니다. `GpuInferenceSimulator`가 다음을 재현합니다.

- `INFERENCE_MAX_CONCURRENCY`: 세마포어 기반 동시 실행 제한
- `INFERENCE_SIMULATED_LATENCY_MS`: 기본 처리 지연
- `INFERENCE_SIMULATED_FAILURE_RATE`: 확률적 실패
- `INFERENCE_BATCH_*`: 마이크로배치 크기·대기 시간·배치 오버헤드
- 요청 `options`의 `simulate_inference_ms`, `simulate_inference_failure_rate`로 건별 재정의

처리기 교체는 `build_primary_processor()` 한 곳에서 이루어지며, `WORKER_PROCESSOR_BACKEND`로 더미 처리기와 전환할 수 있습니다.

## 결과

### 긍정적 결과

- 동시성 2, 지연 900ms 조건으로 추론 병목을 재현해 B 모드 검증에 사용했습니다.
- `inference_*` 지표군(처리 시간, 세마포어 대기, 활성 작업 수, 시뮬레이션 GPU 사용률)을 실제 관측 대상과 동일한 방식으로 노출합니다.
- 실제 추론으로 교체할 때 `TaskProcessorPort` 구현만 바꾸면 됩니다.

### 부정적 결과와 비용

- 측정 결과는 **시뮬레이션 값**입니다. 실제 GPU의 메모리 파편화, 모델 로딩 콜드스타트, 배치 크기별 비선형 처리량은 재현되지 않습니다.
- `inference_simulated_gpu_utilization`은 설정값을 그대로 노출할 뿐 실제 사용률이 아닙니다.

### 후속 작업

- [ ] 실제 추론 백엔드 연결 시 지표 의미 재정의

## 검증 방법

`tests/test_gpu_simulator.py`로 동시성 제한과 배치 동작을 확인하고, 부하 실험에서 설정한 지연·실패율이 지표에 반영되는지 확인합니다.
