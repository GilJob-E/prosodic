import os
import subprocess
import numpy as np
import io
import parselmouth
from parselmouth.praat import call
import matplotlib.pyplot as plt
from scipy import stats
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    print("[Warning] static_ffmpeg not found. Please verify system ffmpeg installation.")
    
class ProsodyAnalyzerLight:
    def __init__(self):
        # 1. 가중치 (Scoring Weights)
        self.weights = {
            "Overall": {
                "avgBand1": -0.120, "intensityMean": 0.065,
                "percentUnvoiced": -0.076, "avgDurPause": -0.090
            },
            "RecommendedHiring": {
                "avgBand1": -0.132, "intensityMean": 0.086,
                "percentUnvoiced": -0.111, "avgDurPause": -0.094
            }
        }

        # 2. 분석 결과를 저장할 멤버변수
        self._gender = None
        self._mean_pitch = None
        self._avg_band1 = None
        self._intensity_mean = None
        self._percent_unvoiced = None
        self._avg_dur_pause = None
        self._scores = None

        # 3. 기준 분포 (Baseline Statistics)
        self.baseline_male = {
            'mean pitch': {'mean': 130.1932, 'std': 15.3799},
            'avgBand1': {'mean': 323.3151, 'std': 58.7594},
            'intensityMean': {'mean': 45.4446, 'std': 9.0125},
            'percentUnvoiced': {'mean': 0.3476, 'std': 0.0623},
            'avgDurPause': {'mean': 0.9950, 'std': 0.1761},
        }
        self.baseline_female = {
            'mean pitch': {'mean': 218.5149, 'std': 21.1525},
            'avgBand1': {'mean': 314.1851, 'std': 42.5445},
            'intensityMean': {'mean': 50.3322, 'std': 5.2173},
            'percentUnvoiced': {'mean': 0.2815, 'std': 0.0440},
            'avgDurPause': {'mean': 1.0560, 'std': 0.3177},
        }
    
    # ==================== Properties ====================
    @property
    def gender(self):
        """분석된 성별 정보 (Male/Female)"""
        return self._gender
    
    @property
    def mean_pitch(self):
        """평균 피치 값"""
        return self._mean_pitch
    
    @property
    def avg_band1(self):
        """F1 대역폭 평균값"""
        return self._avg_band1
    
    @property
    def intensity_mean(self):
        """평균 강도값"""
        return self._intensity_mean
    
    @property
    def percent_unvoiced(self):
        """무성음 비율"""
        return self._percent_unvoiced
    
    @property
    def avg_dur_pause(self):
        """평균 휴지 시간"""
        return self._avg_dur_pause
    
    @property
    def scores(self):
        """분석 점수 (Overall, RecommendedHiring)"""
        return self._scores
    
    def _convert_to_wav_ffmpeg(self, input_path):
        """FFmpeg를 이용해 미디어 파일을 16kHz Mono WAV로 변환"""
        wav_path = "temp_light_analysis.wav"
        if os.path.exists(wav_path): os.remove(wav_path)
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-ar", "16000", "-ac", "1", "-vn", "-f", "wav", wav_path
        ]
        try:
            # stdout/stderr를 숨겨 로그를 깔끔하게 유지
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return wav_path
        except:
            return None

    def _extract_features_light(self, sound):
        """
        핵심 4대 Feature 추출 (Normalization 완료된 Sound 객체 사용)
        """
        duration = sound.get_total_duration()

        # [1] Pitch Analysis
        # Normalization 덕분에 신호가 명확하므로 pitch_floor 50Hz로 저음역대 커버
        pitch = sound.to_pitch(time_step=0.02, pitch_floor=50.0, pitch_ceiling=500.0)
        pitch_vals = pitch.selected_array['frequency']
        
        # 유효 피치 (50Hz 이상)
        pitch_vals_valid = pitch_vals[pitch_vals >= 50.0]
        mean_pitch = np.mean(pitch_vals_valid) if len(pitch_vals_valid) > 0 else 0
        
        # [2] Intensity Analysis
        intensity = sound.to_intensity()
        mean_int = np.mean(intensity.values[0])

        # [3] Formant Analysis (F1)
        # 속도를 위해 Max Freq 3000Hz, Formant 개수 3개로 제한
        formant = sound.to_formant_burg(time_step=0.02, max_number_of_formants=3, maximum_formant=3000)
        
        f1_bw_list = []
        times = np.arange(0, duration, 0.02)
        for t in times:
            bw = formant.get_bandwidth_at_time(1, t)
            if not np.isnan(bw):
                f1_bw_list.append(bw)
        avg_band1 = np.mean(f1_bw_list) if f1_bw_list else 0

        # [4] Pause Analysis (TextGrid)
        # 중요: Normalization이 되었으므로 Silence Threshold -35dB가 매우 안정적으로 작동함
        silence_tier = call(sound, "To TextGrid (silences)", 50.0, 0.0, -35.0, 0.5, 0.1, "silent", "sounding")
        num_intervals = call(silence_tier, "Get number of intervals", 1)
        
        pause_durs = []
        total_silence_dur = 0
        
        for i in range(1, num_intervals + 1):
            label = call(silence_tier, "Get label of interval", 1, i)
            start = call(silence_tier, "Get start time of interval", 1, i)
            end = call(silence_tier, "Get end time of interval", 1, i)
            dur = end - start
            
            if label == "silent":
                pause_durs.append(dur)
                total_silence_dur += dur
        
        avg_dur_pause = np.mean(pause_durs) if pause_durs else 0

        # [5] Unvoiced Rate Correction
        # 침묵(Silence) 구간은 제외하고, '말하고 있는 구간' 내에서의 무성음 비율 계산
        speaking_duration = duration - total_silence_dur
        voiced_duration = len(pitch_vals_valid) * 0.02 # Time step 0.02
        
        if speaking_duration > 0:
            # 이론상 발화시간보다 유성음 시간이 길 수 없으나 오차 보정
            unvoiced_duration = max(0, speaking_duration - voiced_duration)
            percent_unvoiced = unvoiced_duration / speaking_duration
        else:
            percent_unvoiced = 0
            
        # 값 범위 안전장치 (0.0 ~ 1.0)
        percent_unvoiced = min(1.0, max(0.0, percent_unvoiced))

        return {
            "mean pitch": mean_pitch,
            "avgBand1": avg_band1,
            "intensityMean": mean_int,
            "percentUnvoiced": percent_unvoiced,
            "avgDurPause": avg_dur_pause
        }

    def analyze(self, file_path):
        """분석 수행 및 결과를 멤버변수에 저장"""
        wav_path = self._convert_to_wav_ffmpeg(file_path)
        if not wav_path: return False

        try:
            sound = parselmouth.Sound(wav_path)
            # ========================================================
            # [Normalization] -1dB Peak Normalization 적용
            # ========================================================
            # 10^(-1/20) ≈ 0.89125 (Amplitude Scale)
            # 오디오의 최대 진폭을 0.89로 맞춤 -> 분석 기준 통일
            sound.scale_peak(0.89125)
            raw_features = self._extract_features_light(sound)
            
        except Exception as e:
            print(f"[Analysis Error] {e}")
            if os.path.exists(wav_path): os.remove(wav_path)
            return False
        finally:
            if os.path.exists(wav_path): os.remove(wav_path)

        # Gender Detection
        if raw_features["mean pitch"] < 175.0:
            baseline = self.baseline_male
            self._gender = "Male"
        else:
            baseline = self.baseline_female
            self._gender = "Female"

        # 원본 feature 값 저장
        self._mean_pitch = round(raw_features["mean pitch"], 2)
        self._avg_band1 = raw_features["avgBand1"]
        self._intensity_mean = raw_features["intensityMean"]
        self._percent_unvoiced = raw_features["percentUnvoiced"]
        self._avg_dur_pause = raw_features["avgDurPause"]

        # Normalization (Z-Score)
        normalized = {}
        for key, val in raw_features.items():
            if key in baseline:
                stat = baseline[key]
                mu, sigma = stat['mean'], stat['std']
                if sigma == 0: sigma = 1
                normalized[key] = (val - mu) / sigma

        # Scoring
        self._scores = {}
        for category, weights in self.weights.items():
            total = 0
            for feat, weight in weights.items():
                z_val = normalized.get(feat, 0)
                total += z_val * weight
            self._scores[category] = round(total, 4)

        return True

    def get_zscore_visualization(self, save_path=None, return_bytes=False):
        """
        각 feature별 Z-score 정규분포상 위치를 시각화한 그래프 반환
        
        Returns:
            matplotlib.figure.Figure: 생성된 그래프 이미지 객체
        """
        if self._scores is None:
            print("[Error] Analysis not performed. Call analyze() first.")
            return None
        
        # Feature 리스트 및 Z-score 계산
        features = ["avgBand1", "intensityMean", "percentUnvoiced", "avgDurPause"]
        baseline = self.baseline_male if self._gender == "Male" else self.baseline_female
        
        z_scores = {}
        percentiles = {}
        
        for feat in features:
            if feat == "avgBand1":
                raw_val = self._avg_band1
            elif feat == "intensityMean":
                raw_val = self._intensity_mean
            elif feat == "percentUnvoiced":
                raw_val = self._percent_unvoiced
            elif feat == "avgDurPause":
                raw_val = self._avg_dur_pause
            
            stat = baseline[feat]
            mu, sigma = stat['mean'], stat['std']
            if sigma == 0: sigma = 1
            z_score = (raw_val - mu) / sigma
            z_scores[feat] = z_score
            
            # Z-score를 백분위수로 변환 (정규분포 기준)
            percentile = stats.norm.cdf(z_score) * 100
            percentiles[feat] = percentile
        
        # 그래프 생성
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'Feature Z-Score Distribution Analysis ({self._gender})', 
                     fontsize=16, fontweight='bold')
        
        axes = axes.flatten()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
        
        for idx, feat in enumerate(features):
            ax = axes[idx]
            z_score = z_scores[feat]
            percentile = percentiles[feat]
            
            # 정규분포 곡선
            x = np.linspace(-4, 4, 1000)
            y = stats.norm.pdf(x)
            
            ax.plot(x, y, 'k-', linewidth=2, label='Normal Distribution')
            ax.fill_between(x, y, alpha=0.1, color='gray')
            
            # 현재 Z-score 위치 표시
            if -4 <= z_score <= 4:
                y_val = stats.norm.pdf(z_score)
                ax.plot(z_score, y_val, 'o', markersize=12, color=colors[idx], 
                       label=f'Z-Score: {z_score:.2f}')
                ax.axvline(z_score, color=colors[idx], linestyle='--', linewidth=2, alpha=0.7)
                
                # 음영 영역 (Z-score까지의 누적확률)
                x_fill = x[x <= z_score]
                y_fill = stats.norm.pdf(x_fill)
                ax.fill_between(x_fill, y_fill, alpha=0.3, color=colors[idx])
            
            # 레이블 및 제목
            feature_labels = {
                "avgBand1": "F1 Bandwidth (Hz)",
                "intensityMean": "Intensity Mean (dB)",
                "percentUnvoiced": "Unvoiced Ratio",
                "avgDurPause": "Pause Duration (s)"
            }
            
            ax.set_title(f"{feature_labels[feat]}\nPercentile: {percentile:.1f}%", 
                        fontweight='bold', fontsize=12)
            ax.set_xlabel('Z-Score', fontsize=11)
            ax.set_ylabel('Probability Density', fontsize=11)
            ax.set_xlim(-4, 4)
            ax.set_ylim(0, max(y) * 1.1)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=10, loc='upper right')
        
        plt.tight_layout()
        
        # Save to file if requested
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"[Info] Visualization saved to: {save_path}")

        # Return image bytes if requested
        if return_bytes:
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            img_bytes = buf.getvalue()
            buf.close()
            plt.close(fig)
            return img_bytes

        return fig

if __name__ == "__main__":
    # Test Block
    analyzer = ProsodyAnalyzerLight()
    
    # 현재 폴더에 있는 테스트 파일 자동 탐색
    test_files = [f for f in os.listdir('.') if f.endswith(('.wav', '.mp4'))]
    if test_files:
        test_file = test_files[0]
        print(f"Testing with: {test_file}")
        if analyzer.analyze(test_file):
            print(f"Gender: {analyzer.gender}")
            print(f"Mean Pitch: {analyzer.mean_pitch}")
            print(f"Avg Band1: {analyzer.avg_band1}")
            print(f"Intensity Mean: {analyzer.intensity_mean}")
            print(f"Percent Unvoiced: {analyzer.percent_unvoiced}")
            print(f"Avg Duration Pause: {analyzer.avg_dur_pause}")
            print(f"Scores: {analyzer.scores}")
            
            # 시각화 생성
            fig = analyzer.get_zscore_visualization()
            if fig:
                fig.savefig("zscore_visualization.png", dpi=150, bbox_inches='tight')
                print("\n[Info] Visualization saved as 'zscore_visualization.png'")
                plt.show()
        else:
            print("Analysis failed.")
    else:
        print("No test file found in current directory.")