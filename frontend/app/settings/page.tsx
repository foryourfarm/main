'use client';

import { useState, useEffect } from 'react';
import styles from './settings.module.css';

type UserSettings = {
  location: string;
  crops: string[];
};

export default function SettingsPage() {
  const [location, setLocation] = useState('');
  const [crops, setCrops] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const cropOptions = [
    { value: 'apple', label: '사과 🌳' },
    { value: 'pear', label: '배 🌳' },
    { value: 'cucumber', label: '오이 🌾' },
    { value: 'potato', label: '감자 🌾' },
    { value: 'lettuce', label: '상추 🌾' },
  ];

  useEffect(() => {
    // 저장된 설정 로드
    const saved = localStorage.getItem('userSettings');
    if (saved) {
      try {
        const settings = JSON.parse(saved) as UserSettings;
        setLocation(settings.location || '');
        setCrops(settings.crops || []);
      } catch {}
    }
  }, []);

  const toggleCrop = (crop: string) => {
    setCrops((prev) =>
      prev.includes(crop) ? prev.filter((c) => c !== crop) : [...prev, crop]
    );
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!location.trim()) {
      alert('지역을 입력해주세요.');
      return;
    }

    if (crops.length === 0) {
      alert('최소 하나의 작물을 선택해주세요.');
      return;
    }

    setIsLoading(true);
    try {
      // 로컬스토리지에 저장
      const settings: UserSettings = { location, crops };
      localStorage.setItem('userSettings', JSON.stringify(settings));

      // 헤더의 사용자 정보도 업데이트
      const userInfo = {
        name: '농사인',
        location,
      };
      localStorage.setItem('userInfo', JSON.stringify(userInfo));

      alert('설정이 저장되었습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    const saved = localStorage.getItem('userSettings');
    if (saved) {
      try {
        const settings = JSON.parse(saved) as UserSettings;
        setLocation(settings.location || '');
        setCrops(settings.crops || []);
      } catch {}
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <h1 className={styles.title}>설정</h1>

        <form className={styles.form} onSubmit={handleSave}>
          <div className={styles.formGroup}>
            <label className={styles.label}>지역 (시/군)</label>
            <input
              type="text"
              className={styles.input}
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="예: 서울시 강서구"
              required
            />
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>재배 작물 (다중선택)</label>
            <div className={styles.checkboxGroup}>
              {cropOptions.map((option) => (
                <label key={option.value} className={styles.checkboxItem}>
                  <input
                    type="checkbox"
                    checked={crops.includes(option.value)}
                    onChange={() => toggleCrop(option.value)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </div>

          <div className={styles.buttonGroup}>
            <button
              type="submit"
              className={`${styles.button} ${styles.primary}`}
              disabled={isLoading}
            >
              {isLoading ? '저장 중...' : '저장'}
            </button>
            <button
              type="button"
              className={`${styles.button} ${styles.secondary}`}
              onClick={handleReset}
              disabled={isLoading}
            >
              취소
            </button>
          </div>
        </form>

        <footer className={styles.footer}>
          <strong>정보 출처</strong>
          <br />
          기상 데이터: 기상청 실시간·단기예보 | 토양 데이터: 국가 토양도 | 작물 기준:
          농사로 생육 지침
        </footer>
      </div>
    </div>
  );
}
