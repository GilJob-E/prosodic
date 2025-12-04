Prosody Analysis Module (AI Interview Coach)

이 저장소는 면접 영상 및 음성 데이터를 분석하여 발화자의음성 특징(Prosody)을 추출하고,
면접 역량 점수(Overall, Hiring)를 산출하는 Python 모듈입니다.

Praat(Parselmouth) 엔진을 기반으로 하며, 실시간 서비스에 최적화된 4대 핵심 Feature[F1대역폭, 평균멈춤길이, 무성음비율, 평균강도] 분석을 기본으로 제공합니다.

📂 파일 구조 (File Structure)
Plaintext

P_prosody/

├── prosody_analysis.py             # [메인] 고속 분석 모듈 (Core 4 Features)

└── requirements.txt                # 의존성 패키지 목록

🛠️ 설치 및 환경 설정 (Installation)

1. Python 라이브러리 설치
프로젝트 루트에서 다음 명령어를 실행하여 필요한 패키지를 설치합니다.
Bash
pip install -r requirements.txt

3. FFmpeg 설치 (필수 ⭐)
이 모듈은 미디어 변환을 위해 시스템의 FFmpeg를 직접 호출합니다. 따라서 OS에 FFmpeg가 설치되어 있고, 환경 변수(PATH)에 등록되어 있어야 합니다.

Windows: ffmpeg.org에서 다운로드 후 bin 폴더를 시스템 환경 변수 Path에 추가.

Mac: brew install ffmpeg

Linux: sudo apt install ffmpeg

확인 방법: 터미널에 ffmpeg -version을 입력했을 때 버전 정보가 나와야 합니다.


🚀 사용 방법 (Usage)

## 기본 사용법

```python
from prosody_analysis import ProsodyAnalyzerLight

# 1. 분석기 초기화
analyzer = ProsodyAnalyzerLight()

# 2. 파일 분석 (영상 또는 음성 파일 경로)
input_file = "user_upload/interview.mp4"
success = analyzer.analyze(input_file)

# 3. 분석 결과 조회 (프로퍼티로 접근)
if success:
    print(f"성별: {analyzer.gender}")
    print(f"평균 피치: {analyzer.mean_pitch}Hz")
    print(f"F1 대역폭: {analyzer.avg_band1}Hz")
    print(f"평균 강도: {analyzer.intensity_mean}dB")
    print(f"무성음 비율: {analyzer.percent_unvoiced}")
    print(f"평균 휴지 시간: {analyzer.avg_dur_pause}s")
    print(f"종합 점수: {analyzer.scores['Overall']}")
    print(f"고용 추천 점수: {analyzer.scores['RecommendedHiring']}")
else:
    print("분석 실패 (파일 손상 또는 FFmpeg 오류)")
```

## 시각화 (Z-Score 분포 그래프)

```python
# Figure 객체로 받기
fig = analyzer.get_zscore_visualization()
fig.savefig("output.png")

# 또는 직접 파일로 저장
analyzer.get_zscore_visualization(save_path="output.png")

# 또는 이미지 바이트(PNG)로 받기
img_bytes = analyzer.get_zscore_visualization(return_bytes=True)
with open("output.png", "wb") as f:
    f.write(img_bytes)
```
    
# all feature 분석이 필요한 경우
모든 음향 지표(Shimmer, Jitter, Formant Ratio 등)가 필요한 경우 prosody_analysis_all_feature 모듈을 사용합니다.

```python
from prosody_analysis_all_feature import ProsodyAnalyzer

analyzer = ProsodyAnalyzer()
result = analyzer.analyze("interview.mp4")
```

사용법은 `ProsodyAnalyzerLight`와 동일합니다.

# analyze메서드 반환형태 

**변경됨**: `analyze()` 메서드는 더 이상 JSON 딕셔너리를 반환하지 않습니다. 대신 분석 수행 여부(True/False)를 반환하고, 분석 결과는 **멤버변수 프로퍼티**로 제공합니다.

| 프로퍼티 | 반환형 | 설명 |
|---------|--------|------|
| `gender` | str | 자동 감지된 성별 ("Male" \| "Female") |
| `mean_pitch` | float | 성별 감지 기준이 된 평균 피치 (Hz) |
| `avg_band1` | float | F1 대역폭 (Hz) - 목소리 명료도/공명 |
| `intensity_mean` | float | 평균 강도 (dB) |
| `percent_unvoiced` | float | 무성음 비율 (0.0 ~ 1.0) |
| `avg_dur_pause` | float | 평균 휴지 시간 (sec) |
| `scores` | dict | 분석 점수 딕셔너리 {"Overall": float, "RecommendedHiring": float} |

```python
# 사용 예시
analyzer = ProsodyAnalyzerLight()
if analyzer.analyze("audio.wav"):
    print(analyzer.gender)
    print(analyzer.scores)
else:
    print("분석 실패")
```

## 주요 메서드

### 1. `analyze(file_path)` 
음성/영상 파일을 분석하고 결과를 멤버변수에 저장합니다.

**파라미터:**
- `file_path` (str): 분석할 미디어 파일 경로

**반환값:**
- `True`: 분석 성공
- `False`: 분석 실패

**사용 예:**
```python
success = analyzer.analyze("interview.mp4")
```

### 2. `get_zscore_visualization(save_path=None, return_bytes=False)`
각 feature별 Z-score를 정규분포 그래프로 시각화합니다.

**파라미터:**
- `save_path` (str, optional): 이미지 저장 경로 (PNG)
- `return_bytes` (bool): `True`면 PNG 바이트 반환, `False`면 Figure 객체 반환

**반환값:**
- `return_bytes=False`: matplotlib `Figure` 객체
- `return_bytes=True`: PNG 이미지 바이트

**사용 예:**
```python
# 1. Figure 객체로 받아 표시
fig = analyzer.get_zscore_visualization()
plt.show()

# 2. 파일로 직접 저장
analyzer.get_zscore_visualization(save_path="chart.png")

# 3. 바이트로 받아 처리 (웹 서버 등에서 활용)
img_bytes = analyzer.get_zscore_visualization(return_bytes=True)
```

## 분석 로직 상세 (Technical Details)

본 모듈은 일관성 있는 분석 결과를 위해 전처리(Normalization) → 특징 추출 → 성별 감지 → 점수 산출의 파이프라인을 따릅니다.

## 1. 전처리 (Preprocessing)
녹음 환경(마이크 거리, 입력 게인)에 따른 편차를 제거하기 위해 분석 전 오디오를 정규화합니다.
* **Peak Normalization (-1dB):** 입력된 오디오의 최대 진폭을 **-1dB (약 0.89)**로 통일합니다.
* **효과:** * 작게 녹음된 목소리도 표준 크기로 보정됨
  
### 2. 분석 Feature (Light Version)
속도와 정확도의 균형을 위해 다음 4가지 핵심 지표를 추출합니다.
* **F1 Bandwidth:** 목소리의 공명과 명료도를 측정 (Formant 분석).
* **Mean Intensity:** 목소리의 크기 및 에너지 (Normalization 이후의 밀도 측정).
* **Unvoiced Rate:** 순수 발화 시간 중 성대가 울리지 않는(무성음) 구간의 비율.
* **Mean Pause Duration:** 발화 사이의 침묵 길이 (관련 연구 논문에 기반하여 **0.5초 이상** 지속된 침묵만 감지).

### 3. 성별 감지 (Gender Detection)
발화자의 성별에 따라 다른 기준 분포(Baseline)를 적용하기 위해 피치를 분석합니다.
* **기준:** 평균 피치(Mean Pitch) **175Hz**
* **근거:** AI Hub 한국어 음성 데이터 모집단 분포 분석 결과에 기반.
    * `< 175Hz`: **남성(Male)** 기준 데이터 적용
    * `>= 175Hz`: **여성(Female)** 기준 데이터 적용

### 4. 점수 산출 (Scoring)
* **Z-Score Normalization:** 추출된 Raw Data를 성별 기준 분포(Mean, Std)를 이용해 표준화합니다.
* **Weighted Scoring:** 사전에 정의된 가중치(Weights)를 각 지표에 곱하여 최종 **종합 점수(Overall)**와 **고용 추천 점수(Recommended Hiring)**를 도출합니다.

## 기반 연구
본 모듈의 분석 로직과 가중치는 다음 논문을 기반으로 구현 및 튜닝되었습니다.
* Naim, I., Tanveer, M. I., Gildea, D., & Hoque, M. E. (2018). **Automated Analysis and Prediction of Job Interview Performance.** IEEE Transactions on Affective Computing.
